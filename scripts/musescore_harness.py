"""Install and drive a real MuseScore Studio for the integration tests.

Subcommands:

    install         Download MuseScore into the cache and print the executable
    start <score>   Launch MuseScore with a score and the bridge plugin listening
    stop            Kill MuseScore (and the virtual display on Linux)

Works on Linux (AppImage under Xvfb), Windows (MSI) and macOS (DMG). The
version defaults to the newest one in ``tests/integration/musescore-versions.json``
and can be set with ``MUSESCORE_VERSION``; its release asset is looked up
through the GitHub releases API (``GITHUB_TOKEN`` raises the rate limit)
unless ``MUSESCORE_DOWNLOAD_URL`` names it directly. ``MUSESCORE_CACHE_DIR``
is where downloads and the unpacked application live.

``start`` rewrites MuseScore's user configuration (plugin, shortcut,
first-launch flags), so use a throwaway home directory on a machine where
MuseScore is used for real.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import websockets
from websockets.exceptions import WebSocketException

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger("musescore-harness")

# ── Defaults ──────────────────────────────────────────────────────────

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = REPOSITORY_ROOT / "tests" / "integration" / "musescore-versions.json"
RELEASES_API_URL = "https://api.github.com/repos/musescore/MuseScore/releases/tags"
# The release asset for each platform, by how its file name ends.
RELEASE_ASSET_SUFFIXES: dict[str, str] = {
    "Linux": "-x86_64.AppImage",
    "Windows": "-x86_64.msi",
    "Darwin": ".dmg",
}

BRIDGE_PORT = 8765
BRIDGE_TIMEOUT_SECONDS = 60.0
BRIDGE_POLL_INTERVAL_SECONDS = 2.0
BRIDGE_ROUND_TRIP_SECONDS = 2.0
STARTUP_SECONDS = 45.0
LAUNCH_ATTEMPTS = 2
DIALOG_DISMISS_SECONDS = 2.0
LOG_TAIL_LINES = 40

PLUGIN_FILE = "mcp-score-bridge.qml"
PLUGIN_SOURCE = REPOSITORY_ROOT / "src" / "mcp_score" / "musescore" / "plugin.qml"
# Bound to every action-code form MuseScore 4 has used for a plugin:
# muse://...?action=main in 4.4, action://...?action=main from 4.5.
PLUGIN_ACTION_CODES = (
    f"muse://extensions/v1/{PLUGIN_FILE}?action=main",
    f"musescore://extensions/v1/{PLUGIN_FILE}?action=main",
    f"action://extensions/v1/{PLUGIN_FILE}?action=main",
)
# MuseScore 4.4 identifies plugins with a muse:// URI, 4.5 and later with
# musescore://; each version ignores the entry it does not know.
PLUGIN_URIS = (
    f"muse://extensions/v1/{PLUGIN_FILE}",
    f"musescore://extensions/v1/{PLUGIN_FILE}",
)
PLUGIN_SHORTCUT = "Ctrl+Shift+F12"

# Linux only: the virtual display. Not :99, which is the first display
# xvfb-run picks; the render tests run under xvfb-run in the same CI job.
XVFB_DISPLAY = os.environ.get("MUSESCORE_DISPLAY", ":87")
XVFB_SCREEN = "1600x1000x24"
XVFB_STARTUP_SECONDS = 10.0
# xdotool clicks here to focus the score view before sending the shortcut.
SCORE_VIEW_CLICK = (700, 400)

UNREACHABLE_ERRORS: tuple[type[Exception], ...] = (
    OSError,
    WebSocketException,
    TimeoutError,
)


class HarnessError(Exception):
    """A step of the harness failed; the message is meant for the console."""


# ── Platform layout ───────────────────────────────────────────────────

# Preferences that keep MuseScore from opening dialogs over the score
# window: the first-launch wizard and the "What's new" welcome dialog.
# MuseScore forces the welcome dialog back on whenever the last version it
# was shown for is older than the running one, so that version is set far
# into the future. Keys are Qt settings paths.
STARTUP_PREFERENCES: dict[str, bool | str] = {
    "application/hasCompletedFirstLaunchSetup": True,
    "application/welcomeDialogShowOnStartup": False,
    "application/welcomeDialogLastShownVersion": "99.0.0",
}
MACOS_PREFERENCES_DOMAIN = "org.musescore.MuseScore4"


class PreferencesStore(Protocol):
    """Where MuseScore's main preferences live on a platform."""

    def write(self, preferences: Mapping[str, bool | str]) -> None:
        """Store *preferences* (Qt settings paths to values) for MuseScore."""


@dataclass(frozen=True)
class IniPreferences:
    """A Qt ini file, as MuseScore uses on Linux and Windows."""

    file: Path

    def write(self, preferences: Mapping[str, bool | str]) -> None:
        sections: dict[str, list[str]] = {}
        for path, value in preferences.items():
            section, _, key = path.rpartition("/")
            sections.setdefault(section, []).append(f"{key}={_ini_value(value)}")
        text = "".join(
            f"[{section}]\n" + "".join(f"{line}\n" for line in lines)
            for section, lines in sections.items()
        )
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(text)


def _ini_value(value: bool | str) -> str:
    return str(value).lower() if isinstance(value, bool) else value


@dataclass(frozen=True)
class MacOSPreferences:
    """The native preferences domain Qt uses on macOS.

    macOS caches preferences in cfprefsd, so the plist under
    ~/Library/Preferences is written through ``defaults`` rather than
    directly. Qt stores a settings path ``a/b`` under the key ``a.b``.
    """

    domain: str

    def write(self, preferences: Mapping[str, bool | str]) -> None:
        for path, value in preferences.items():
            key = path.replace("/", ".")
            typed = (
                ["-bool", str(value).lower()]
                if isinstance(value, bool)
                else ["-string", value]
            )
            run(["defaults", "write", self.domain, key, *typed])


@dataclass(frozen=True)
class Layout:
    """Where MuseScore keeps things on this platform, and how to get it."""

    system: str
    preferences: PreferencesStore
    data_dir: Path
    plugins_dir: Path
    stdout_log: Path

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"


def layout_for(system: str, home: Path) -> Layout:
    """MuseScore's preferences, data and plugin locations for *system*.

    MuseScore keeps its main preferences in a Qt ini file on Linux and
    Windows and in the native preferences domain on macOS; its data lives
    under Qt's app-local data location on every platform.
    """
    documents = home / "Documents" / "MuseScore4" / "Plugins"
    temp = Path(tempfile.gettempdir()) / "mcp-score-musescore.log"
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        preferences = IniPreferences(appdata / "MuseScore" / "MuseScore4.ini")
        return Layout(
            system, preferences, local / "MuseScore" / "MuseScore4", documents, temp
        )
    if system == "Darwin":
        data = home / "Library" / "Application Support" / "MuseScore" / "MuseScore4"
        return Layout(
            system, MacOSPreferences(MACOS_PREFERENCES_DOMAIN), data, documents, temp
        )
    preferences = IniPreferences(home / ".config" / "MuseScore" / "MuseScore4.ini")
    data = home / ".local" / "share" / "MuseScore" / "MuseScore4"
    return Layout(system, preferences, data, documents, temp)


def latest_version(versions_file: Path) -> str:
    """The newest MuseScore version listed in *versions_file*."""
    versions: dict[str, str] = json.loads(versions_file.read_text())
    return versions["latest"]


def fetch_json(url: str) -> Any:
    """GET *url* and decode the JSON body, sending the GitHub token if set."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.load(response)


def release_asset_url(system: str, version: str) -> str:
    """The download URL of the *version* release asset for *system*.

    Asset names carry a build number (``MuseScore-Studio-4.7.5.260831071.dmg``)
    that only the release itself knows, so the release is looked up through
    the GitHub API and the asset chosen by its platform suffix.
    """
    suffix = RELEASE_ASSET_SUFFIXES[system]
    release = fetch_json(f"{RELEASES_API_URL}/v{version}")
    assets: list[dict[str, Any]] = release.get("assets", [])
    for asset in assets:
        if str(asset["name"]).endswith(suffix):
            return str(asset["browser_download_url"])
    raise HarnessError(f"release v{version} has no asset ending in {suffix}")


@dataclass(frozen=True)
class Settings:
    """Everything the harness needs, resolved from the environment."""

    system: str
    version: str
    cache_dir: Path
    layout: Layout
    download_url: str | None = None
    """An explicit asset URL; otherwise the release is looked up on demand."""

    @classmethod
    def from_environment(cls) -> Settings:
        system = platform.system()
        version = os.environ.get("MUSESCORE_VERSION") or latest_version(VERSIONS_FILE)
        cache_dir = Path(
            os.environ.get(
                "MUSESCORE_CACHE_DIR",
                Path.home() / ".cache" / "mcp-score" / f"musescore-{version}",
            )
        )
        layout = layout_for(system, Path.home())
        url = os.environ.get("MUSESCORE_DOWNLOAD_URL") or None
        return cls(system, version, cache_dir, layout, url)

    def resolve_download_url(self) -> str:
        return self.download_url or release_asset_url(self.system, self.version)

    @property
    def executable(self) -> Path:
        """Where the MuseScore executable is once ``install`` has run."""
        if self.system == "Windows":
            program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            return program_files / "MuseScore 4" / "bin" / "MuseScore4.exe"
        if self.system == "Darwin":
            return self.cache_dir / "MuseScore 4.app" / "Contents" / "MacOS" / "mscore"
        return self.cache_dir / "squashfs-root" / "AppRun"


# ── install ───────────────────────────────────────────────────────────


def download(url: str, destination: Path) -> None:
    logger.info("downloading %s", url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(response, out)


def install(settings: Settings) -> Path:
    """Make MuseScore available and return its executable."""
    executable = settings.executable
    if executable.exists():
        logger.info("MuseScore Studio %s already installed", settings.version)
        return executable

    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    if settings.system == "Windows":
        installer = settings.cache_dir / "MuseScore.msi"
        if not installer.exists():
            download(settings.resolve_download_url(), installer)
        logger.info("installing %s silently", installer.name)
        run(["msiexec", "/i", str(installer), "/qn", "ALLUSERS=1"])
    elif settings.system == "Darwin":
        image = settings.cache_dir / "MuseScore.dmg"
        if not image.exists():
            download(settings.resolve_download_url(), image)
        mount_point = settings.cache_dir / "mnt"
        logger.info("mounting %s", image.name)
        run(
            [
                "hdiutil",
                "attach",
                "-nobrowse",
                "-quiet",
                "-mountpoint",
                str(mount_point),
                str(image),
            ]
        )
        try:
            shutil.copytree(
                mount_point / "MuseScore 4.app", settings.cache_dir / "MuseScore 4.app"
            )
        finally:
            run(["hdiutil", "detach", "-quiet", str(mount_point)])
        # Files copied out of a downloaded image carry the quarantine flag.
        run(
            [
                "xattr",
                "-dr",
                "com.apple.quarantine",
                str(settings.cache_dir / "MuseScore 4.app"),
            ],
            check=False,
        )
    else:
        appimage = settings.cache_dir / "MuseScore.AppImage"
        download(settings.resolve_download_url(), appimage)
        appimage.chmod(0o755)
        # Extracting avoids needing FUSE, which CI runners and containers lack.
        logger.info("extracting AppImage")
        run([str(appimage), "--appimage-extract"], cwd=settings.cache_dir)
        appimage.unlink()

    if not executable.exists():
        raise HarnessError(f"installation did not produce {executable}")
    return executable


# ── start ─────────────────────────────────────────────────────────────


def seed_configuration(layout: Layout) -> None:
    """Install the plugin and configure MuseScore to run it on a shortcut.

    Plugins cannot be started from the command line (``--test-case`` runs
    MuseScore in console mode without a GUI), so the plugin is enabled and
    bound to a keyboard shortcut that ``start`` presses after launch.
    """
    layout.plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLUGIN_SOURCE, layout.plugins_dir / PLUGIN_FILE)

    layout.preferences.write(STARTUP_PREFERENCES)

    extensions_dir = layout.data_dir / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    enabled = [
        {"uri": uri, "actions": [{"code": "main", "exec_point": "manually"}]}
        for uri in PLUGIN_URIS
    ]
    (extensions_dir / "config.json").write_text(json.dumps(enabled))

    bindings = "".join(
        f"  <SC>\n    <key>{code}</key>\n    <seq>{PLUGIN_SHORTCUT}</seq>\n  </SC>\n"
        for code in PLUGIN_ACTION_CODES
    )
    (layout.data_dir / "shortcuts.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Shortcuts>\n{bindings}</Shortcuts>\n'
    )

    # A leftover session from a previous (killed) run makes MuseScore ask
    # whether to restore it, and that modal dialog steals focus.
    shutil.rmtree(layout.data_dir / "session", ignore_errors=True)


def start_xvfb() -> None:
    """Start the virtual X display (Linux only) and wait for its socket."""
    socket = Path("/tmp/.X11-unix") / f"X{XVFB_DISPLAY[1:]}"  # noqa: S108
    if xvfb_running() and socket.exists():
        logger.info("Xvfb already running on %s", XVFB_DISPLAY)
        return
    # A server without its socket is one that is still shutting down.
    stop_xvfb()
    socket.unlink(missing_ok=True)
    logger.info("starting Xvfb on %s", XVFB_DISPLAY)
    subprocess.Popen(  # noqa: S603
        ["Xvfb", XVFB_DISPLAY, "-screen", "0", XVFB_SCREEN],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + XVFB_STARTUP_SECONDS
    while not socket.exists():
        if time.monotonic() > deadline:
            raise HarnessError(f"Xvfb did not come up on {XVFB_DISPLAY}")
        time.sleep(0.5)


def xvfb_running() -> bool:
    return run(["pgrep", "-f", f"^Xvfb {XVFB_DISPLAY} "], check=False).returncode == 0


def stop_xvfb() -> None:
    run(["pkill", "-f", f"^Xvfb {XVFB_DISPLAY} "], check=False)


def launch(settings: Settings, score: Path) -> subprocess.Popen[bytes]:
    """Start MuseScore with *score* open and give it time to load.

    MuseScore Studio 4.7 on macOS 26 occasionally aborts a few seconds into
    startup (crashpad reports a kernel failure) and starts fine the next
    time, so a launch that dies during startup is tried once more.
    """
    if musescore_running(settings):
        raise HarnessError("MuseScore is already running; run 'stop' first")
    for attempt in range(1, LAUNCH_ATTEMPTS + 1):
        process = _start(settings, score)
        time.sleep(STARTUP_SECONDS)
        if process.poll() is None:
            return process
        logger.warning("MuseScore exited during startup (attempt %d)", attempt)
    print_log_tails(settings.layout)
    raise HarnessError("MuseScore exited during startup")


def _start(settings: Settings, score: Path) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    if settings.system == "Linux":
        env["DISPLAY"] = XVFB_DISPLAY
    logger.info(
        "launching MuseScore with %s (waiting %.0fs for it to load)",
        score,
        STARTUP_SECONDS,
    )
    stdout_log = settings.layout.stdout_log.open("wb")
    return subprocess.Popen(  # noqa: S603
        [str(settings.executable), str(score)],
        stdout=stdout_log,
        stderr=subprocess.STDOUT,
        env=env,
    )


def trigger_plugin(settings: Settings) -> None:
    """Press the plugin shortcut in the MuseScore window.

    The shortcut only reaches the plugin action when the score view has
    keyboard focus, so the window is activated and clicked first. Escape
    closes any dialog that still came up.
    """
    logger.info("triggering the bridge plugin with %s", PLUGIN_SHORTCUT)
    if settings.system == "Windows":
        run(["powershell", "-NoProfile", "-Command", WINDOWS_TRIGGER_SCRIPT])
    elif settings.system == "Darwin":
        run(["osascript", "-e", MACOS_TRIGGER_SCRIPT])
    else:
        env = {**os.environ, "DISPLAY": XVFB_DISPLAY}
        found = run(["xdotool", "search", "--name", "MuseScore"], env=env, check=False)
        windows = found.stdout.split()
        if not windows:
            print_log_tails(settings.layout)
            raise HarnessError(f"no MuseScore window found on {XVFB_DISPLAY}")
        window = windows[-1]
        # Without a window manager (bare Xvfb) windowactivate fails; fall back
        # to windowfocus and rely on the click below.
        if run(
            ["xdotool", "windowactivate", "--sync", window], env=env, check=False
        ).returncode:
            run(["xdotool", "windowfocus", "--sync", window], env=env, check=False)
        run(["xdotool", "key", "--clearmodifiers", "Escape"], env=env)
        time.sleep(DIALOG_DISMISS_SECONDS)
        x, y = SCORE_VIEW_CLICK
        run(["xdotool", "mousemove", str(x), str(y), "click", "1"], env=env)
        run(["xdotool", "key", "--clearmodifiers", "ctrl+shift+F12"], env=env)


WINDOWS_TRIGGER_SCRIPT = r"""
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Native {
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint f, uint x, uint y, uint d, UIntPtr e);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$windows = Get-Process MuseScore4 | Where-Object { $_.MainWindowHandle -ne 0 }
$process = $windows | Select-Object -First 1
if (-not $process) { throw "no MuseScore window" }
[Native]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Seconds 2
$rect = New-Object Native+RECT
[Native]::GetWindowRect($process.MainWindowHandle, [ref]$rect) | Out-Null
$x = [int](($rect.Left + $rect.Right) * 0.6)
$y = [int](($rect.Top + $rect.Bottom) * 0.5)
[Native]::SetCursorPos($x, $y) | Out-Null
[Native]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
[Native]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("^+{F12}")
"""

# Qt reads "Ctrl" in a shortcut as the Command key on macOS, so the
# shortcut bound as Ctrl+Shift+F12 is pressed as Command+Shift+F12 there.
# Key code 53 is Escape, 111 is F12.
MACOS_TRIGGER_SCRIPT = """
tell application "MuseScore 4" to activate
delay 1
tell application "System Events"
    key code 53
    delay 2
    click at {700, 400}
    delay 1
    key code 111 using {command down, shift down}
end tell
"""


async def ping_once(uri: str) -> bool:
    """Return True if the bridge at *uri* answers a ping with ``pong``."""
    try:
        async with websockets.connect(
            uri, open_timeout=BRIDGE_ROUND_TRIP_SECONDS
        ) as connection:
            await connection.send(json.dumps({"command": "ping"}))
            raw = await asyncio.wait_for(
                connection.recv(), timeout=BRIDGE_ROUND_TRIP_SECONDS
            )
    except UNREACHABLE_ERRORS:
        return False
    try:
        response: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return response.get("result") == "pong"


async def wait_for_bridge(uri: str, timeout_seconds: float) -> bool:
    """Poll with a real ping: the port can be open before the plugin answers."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        if await ping_once(uri):
            return True
        if time.monotonic() > deadline:
            return False
        await asyncio.sleep(BRIDGE_POLL_INTERVAL_SECONDS)


def start(settings: Settings, score: Path) -> None:
    if not settings.executable.exists():
        raise HarnessError(f"{settings.executable} not found; run 'install' first")
    seed_configuration(settings.layout)
    if settings.system == "Linux":
        start_xvfb()
    launch(settings, score.resolve())
    trigger_plugin(settings)
    uri = f"ws://localhost:{BRIDGE_PORT}"
    logger.info("waiting up to %.0fs for the bridge at %s", BRIDGE_TIMEOUT_SECONDS, uri)
    if not asyncio.run(wait_for_bridge(uri, BRIDGE_TIMEOUT_SECONDS)):
        print_log_tails(settings.layout)
        raise HarnessError(f"the bridge plugin did not answer at {uri}")
    logger.info("bridge ready at %s", uri)


# ── stop ──────────────────────────────────────────────────────────────


def musescore_process_pattern(system: str) -> str:
    """What identifies a MuseScore process on *system*."""
    if system == "Windows":
        return "MuseScore4.exe"
    if system == "Darwin":
        return "MuseScore 4.app/Contents/MacOS/mscore"
    # The AppImage's binary renames its process, so match the command line.
    return "bin/mscore4portable"


def musescore_running(settings: Settings) -> bool:
    pattern = musescore_process_pattern(settings.system)
    if settings.system == "Windows":
        listing = run(["tasklist", "/FI", f"IMAGENAME eq {pattern}"], check=False)
        return pattern.lower() in listing.stdout.lower()
    return run(["pgrep", "-f", pattern], check=False).returncode == 0


def stop(settings: Settings) -> None:
    logger.info("stopping MuseScore")
    pattern = musescore_process_pattern(settings.system)
    if settings.system == "Windows":
        run(["taskkill", "/F", "/IM", pattern], check=False)
    else:
        run(["pkill", "-f", pattern], check=False)
    if settings.system == "Linux":
        stop_xvfb()


# ── Helpers ───────────────────────────────────────────────────────────


def run(
    command: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603
        command, check=False, cwd=cwd, env=env, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise HarnessError(
            f"{command[0]} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result


def newest_log(layout: Layout) -> Path | None:
    logs = sorted(layout.log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def print_log_tails(layout: Layout) -> None:
    for path in (newest_log(layout), layout.stdout_log):
        if path is None or not path.exists():
            continue
        lines = path.read_text(errors="replace").splitlines()[-LOG_TAIL_LINES:]
        logger.info("tail of %s:\n%s", path, "\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("install")
    start_parser = commands.add_parser("start")
    start_parser.add_argument("score", type=Path)
    commands.add_parser("stop")
    args = parser.parse_args(argv)

    settings = Settings.from_environment()
    try:
        if args.command == "install":
            print(install(settings))  # noqa: T201
        elif args.command == "start":
            start(settings, args.score)
        else:
            stop(settings)
    except HarnessError as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
