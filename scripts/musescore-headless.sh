#!/usr/bin/env bash
#
# Run MuseScore Studio headlessly on Linux for the integration tests.
#
#   scripts/musescore-headless.sh install          Download and extract the AppImage;
#                                                  print the launcher (AppRun) path.
#   scripts/musescore-headless.sh start <score>    Start Xvfb, launch the MuseScore GUI
#                                                  with <score> open and the bridge
#                                                  plugin listening on ws://localhost:8765.
#   scripts/musescore-headless.sh stop             Kill MuseScore and Xvfb.
#
# Configuration (environment variables, all optional):
#   MUSESCORE_VERSION       MuseScore Studio version (default: 4.7.5)
#   MUSESCORE_APPIMAGE_URL  AppImage download URL for that version
#   MUSESCORE_CACHE_DIR     Where the extracted AppImage is kept
#                           (default: ~/.cache/mcp-score/musescore-<version>)
#   PYTHON                  Interpreter with the `websockets` package, used to
#                           poll the bridge (default: python3)
#
# `start` writes MuseScore's user configuration under ~/.config/MuseScore and
# ~/.local/share/MuseScore, so run it on a CI runner or with a throwaway HOME.
set -euo pipefail

MUSESCORE_VERSION="${MUSESCORE_VERSION:-4.7.5}"
MUSESCORE_APPIMAGE_URL="${MUSESCORE_APPIMAGE_URL:-https://github.com/musescore/MuseScore/releases/download/v4.7.5/MuseScore-Studio-4.7.5.260831071-x86_64.AppImage}"
MUSESCORE_CACHE_DIR="${MUSESCORE_CACHE_DIR:-$HOME/.cache/mcp-score/musescore-$MUSESCORE_VERSION}"
PYTHON="${PYTHON:-python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(dirname "$SCRIPT_DIR")"
WAIT_FOR_BRIDGE_SCRIPT="$SCRIPT_DIR/wait_for_bridge.py"
PLUGIN_SOURCE="$REPOSITORY_ROOT/src/mcp_score/musescore/plugin.qml"

APPIMAGE_PATH="$MUSESCORE_CACHE_DIR/MuseScore.AppImage"
APP_RUN="$MUSESCORE_CACHE_DIR/squashfs-root/AppRun"
# AppRun runs squashfs-root/bin/mscore4portable, which renames its process to
# "main", so it is found by command line (pgrep/pkill -f), not by name.
MUSESCORE_PROCESS_PATTERN="bin/mscore4portable"
MUSESCORE_STDOUT_LOG="${TMPDIR:-/tmp}/mcp-score-musescore.log"

# MuseScore's user configuration. The plugin directory matches _PLUGIN_DIRS in
# src/mcp_score/cli.py (what `mcp-score install-plugin` uses on Linux).
MUSESCORE_PLUGIN_DIR="$HOME/Documents/MuseScore4/Plugins"
MUSESCORE_PLUGIN_FILE="mcp-score-bridge.qml"
MUSESCORE_SETTINGS_FILE="$HOME/.config/MuseScore/MuseScore4.ini"
MUSESCORE_DATA_DIR="$HOME/.local/share/MuseScore/MuseScore4"
MUSESCORE_LOG_DIR="$MUSESCORE_DATA_DIR/logs"

# Not :99, which is the first display xvfb-run picks: the render tests run
# under xvfb-run in the same job and must not collide with this server.
DISPLAY_NUMBER="${MUSESCORE_DISPLAY_NUMBER:-87}"
XVFB_DISPLAY=":$DISPLAY_NUMBER"
XVFB_SCREEN="1600x1000x24"
XVFB_SOCKET="/tmp/.X11-unix/X$DISPLAY_NUMBER"
XVFB_STARTUP_SECONDS=10

BRIDGE_PORT=8765
# The same shortcut in MuseScore's shortcuts.xml notation and in xdotool's.
PLUGIN_SHORTCUT_MUSESCORE="Ctrl+Shift+F12"
PLUGIN_SHORTCUT_XDOTOOL="ctrl+shift+F12"
# The plugin action is only enabled once a project is open, so give the GUI
# time to load the score before triggering it.
MUSESCORE_STARTUP_SECONDS=45
DIALOG_DISMISS_SECONDS=2
BRIDGE_TIMEOUT_SECONDS=60
LOG_TAIL_LINES=40

log() {
    echo "[musescore-headless] $*" >&2
}

die() {
    log "error: $*"
    exit 1
}

usage() {
    sed -n '2,/^set -euo pipefail/{/^set -euo pipefail/d;s/^# \{0,1\}//p}' "${BASH_SOURCE[0]}" >&2
    exit 2
}

newest_musescore_log() {
    # MuseScore writes one timestamped log per launch. Print the newest, if any.
    find "$MUSESCORE_LOG_DIR" -maxdepth 1 -name '*.log' -printf '%T@ %p\n' 2>/dev/null \
        | sort -n | tail -1 | cut -d' ' -f2-
}

print_log_tails() {
    local musescore_log
    musescore_log="$(newest_musescore_log)"
    if [ -n "$musescore_log" ]; then
        log "tail of $musescore_log:"
        tail -n "$LOG_TAIL_LINES" "$musescore_log" >&2
    else
        log "no MuseScore log found under $MUSESCORE_LOG_DIR"
    fi
    if [ -f "$MUSESCORE_STDOUT_LOG" ]; then
        log "tail of $MUSESCORE_STDOUT_LOG:"
        tail -n "$LOG_TAIL_LINES" "$MUSESCORE_STDOUT_LOG" >&2
    fi
}

# ── install ───────────────────────────────────────────────────────────

install() {
    if [ -x "$APP_RUN" ]; then
        log "MuseScore Studio $MUSESCORE_VERSION already extracted in $MUSESCORE_CACHE_DIR"
        echo "$APP_RUN"
        return
    fi
    mkdir -p "$MUSESCORE_CACHE_DIR"
    log "downloading MuseScore Studio $MUSESCORE_VERSION"
    curl --fail --silent --show-error --location --retry 3 \
        --output "$APPIMAGE_PATH" "$MUSESCORE_APPIMAGE_URL"
    chmod +x "$APPIMAGE_PATH"
    # Extracting avoids needing FUSE, which CI runners and containers lack.
    # --appimage-extract always unpacks into ./squashfs-root.
    log "extracting AppImage"
    (cd "$MUSESCORE_CACHE_DIR" && "$APPIMAGE_PATH" --appimage-extract >/dev/null)
    rm -f "$APPIMAGE_PATH"
    [ -x "$APP_RUN" ] || die "extraction did not produce $APP_RUN"
    echo "$APP_RUN"
}

# ── start ─────────────────────────────────────────────────────────────

seed_musescore_configuration() {
    log "installing the bridge plugin and seeding MuseScore configuration"
    mkdir -p "$MUSESCORE_PLUGIN_DIR"
    cp "$PLUGIN_SOURCE" "$MUSESCORE_PLUGIN_DIR/$MUSESCORE_PLUGIN_FILE"

    # Skip the first-launch wizard and the "What's new" welcome dialog; both
    # would steal focus from the score window and block the keyboard
    # shortcut. MuseScore forces the welcome dialog back on whenever the
    # last version it was shown for is older than the running one, so the
    # recorded version is set far into the future.
    mkdir -p "$(dirname "$MUSESCORE_SETTINGS_FILE")"
    cat >"$MUSESCORE_SETTINGS_FILE" <<'EOF'
[application]
hasCompletedFirstLaunchSetup=true
welcomeDialogShowOnStartup=false
welcomeDialogLastShownVersion=99.0.0
EOF

    # Enable the plugin (the equivalent of Plugins > Manage Plugins > Enable)
    # and bind it to a keyboard shortcut. Plugins cannot be started from the
    # command line: `--test-case` runs MuseScore in console mode without a
    # GUI, so the shortcut sent through xdotool is the way to run it.
    # MuseScore 4.4 identifies plugins with a muse:// URI, 4.5 and later
    # with musescore://; each version ignores the entry it does not know.
    mkdir -p "$MUSESCORE_DATA_DIR/extensions"
    cat >"$MUSESCORE_DATA_DIR/extensions/config.json" <<EOF
[{"uri":"muse://extensions/v1/$MUSESCORE_PLUGIN_FILE","actions":[{"code":"main","exec_point":"manually"}]},
 {"uri":"musescore://extensions/v1/$MUSESCORE_PLUGIN_FILE","actions":[{"code":"main","exec_point":"manually"}]}]
EOF
    # The action code that runs a plugin changed across 4.x releases:
    # muse://...?action=main in 4.4, action://...?action=main from 4.5.
    # MuseScore ignores shortcuts for codes it does not know, so every
    # known form is bound to the same key.
    cat >"$MUSESCORE_DATA_DIR/shortcuts.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<Shortcuts>
  <SC>
    <key>muse://extensions/v1/$MUSESCORE_PLUGIN_FILE?action=main</key>
    <seq>$PLUGIN_SHORTCUT_MUSESCORE</seq>
  </SC>
  <SC>
    <key>musescore://extensions/v1/$MUSESCORE_PLUGIN_FILE?action=main</key>
    <seq>$PLUGIN_SHORTCUT_MUSESCORE</seq>
  </SC>
  <SC>
    <key>action://extensions/v1/$MUSESCORE_PLUGIN_FILE?action=main</key>
    <seq>$PLUGIN_SHORTCUT_MUSESCORE</seq>
  </SC>
</Shortcuts>
EOF

    # A leftover session from a previous (killed) run makes MuseScore ask
    # whether to restore it, and that modal dialog steals focus.
    rm -rf "$MUSESCORE_DATA_DIR/session"
}

start_xvfb() {
    # MuseScore needs a real X display even for headless work (it initialises
    # GTK, which QT_QPA_PLATFORM=offscreen does not satisfy), so run it under Xvfb.
    if pgrep -f "^Xvfb $XVFB_DISPLAY " >/dev/null && [ -S "$XVFB_SOCKET" ]; then
        log "Xvfb already running on $XVFB_DISPLAY"
    else
        # A server without its socket is one that is still shutting down.
        pkill -f "^Xvfb $XVFB_DISPLAY " 2>/dev/null || true
        # A killed Xvfb can leave its socket behind, which would make the new
        # server refuse the display.
        rm -f "$XVFB_SOCKET"
        log "starting Xvfb on $XVFB_DISPLAY"
        Xvfb "$XVFB_DISPLAY" -screen 0 "$XVFB_SCREEN" >/dev/null 2>&1 &
    fi
    local waited=0
    while [ ! -S "$XVFB_SOCKET" ]; do
        [ "$waited" -lt "$XVFB_STARTUP_SECONDS" ] || die "Xvfb did not come up on $XVFB_DISPLAY"
        sleep 1
        waited=$((waited + 1))
    done
}

launch_musescore() {
    local score_path="$1"
    if pgrep -f "$MUSESCORE_PROCESS_PATTERN" >/dev/null; then
        die "MuseScore is already running; run '$0 stop' first"
    fi
    log "launching MuseScore with $score_path (waiting ${MUSESCORE_STARTUP_SECONDS}s for it to load)"
    "$APP_RUN" "$score_path" >"$MUSESCORE_STDOUT_LOG" 2>&1 &
    sleep "$MUSESCORE_STARTUP_SECONDS"
    pgrep -f "$MUSESCORE_PROCESS_PATTERN" >/dev/null || {
        print_log_tails
        die "MuseScore exited during startup"
    }
}

trigger_plugin() {
    local window_id
    window_id="$(xdotool search --name MuseScore 2>/dev/null | tail -1 || true)"
    [ -n "$window_id" ] || {
        print_log_tails
        die "no MuseScore window found on $XVFB_DISPLAY"
    }
    log "triggering the bridge plugin with $PLUGIN_SHORTCUT_MUSESCORE"
    # Focus the score view first: the shortcut only reaches the plugin action
    # when the main window has keyboard focus. Without a window manager (bare
    # Xvfb) windowactivate reports an error, so fall back to windowfocus and
    # rely on the click below to focus the score view.
    xdotool windowactivate --sync "$window_id" 2>/dev/null \
        || xdotool windowfocus --sync "$window_id" 2>/dev/null \
        || log "could not focus window $window_id, relying on the click"
    # MuseScore shows its modal welcome dialog regardless of the settings
    # file; Escape dismisses it (and is harmless when nothing is open).
    xdotool key --clearmodifiers Escape
    sleep "$DIALOG_DISMISS_SECONDS"
    xdotool mousemove 700 400 click 1
    xdotool key --clearmodifiers "$PLUGIN_SHORTCUT_XDOTOOL"
}

wait_for_bridge() {
    # Poll with a real WebSocket ping rather than checking the port: the
    # port can be open before the plugin answers commands.
    log "waiting up to ${BRIDGE_TIMEOUT_SECONDS}s for the bridge on port $BRIDGE_PORT"
    "$PYTHON" "$WAIT_FOR_BRIDGE_SCRIPT" --port "$BRIDGE_PORT" --timeout "$BRIDGE_TIMEOUT_SECONDS" || {
        print_log_tails
        die "the bridge plugin did not answer on ws://localhost:$BRIDGE_PORT"
    }
}

start() {
    [ $# -eq 1 ] || usage
    local score_path
    score_path="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
    [ -f "$score_path" ] || die "score file not found: $score_path"
    [ -x "$APP_RUN" ] || die "MuseScore not installed; run '$0 install' first"

    export DISPLAY="$XVFB_DISPLAY"
    seed_musescore_configuration
    start_xvfb
    launch_musescore "$score_path"
    trigger_plugin
    wait_for_bridge
    log "bridge ready on ws://localhost:$BRIDGE_PORT (DISPLAY=$XVFB_DISPLAY)"
}

# ── stop ──────────────────────────────────────────────────────────────

stop() {
    log "stopping MuseScore and Xvfb"
    pkill -f "$MUSESCORE_PROCESS_PATTERN" || true
    pkill -f "^Xvfb $XVFB_DISPLAY " || true
}

# ── entry point ───────────────────────────────────────────────────────

[ $# -ge 1 ] || usage
subcommand="$1"
shift
case "$subcommand" in
    install) install "$@" ;;
    start) start "$@" ;;
    stop) stop "$@" ;;
    *) usage ;;
esac
