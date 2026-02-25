"""Score state manager — builds and modifies scores using music21."""

import logging
import re
from typing import Any

from music21 import bar, expressions, harmony, key, meter, note, stream, tempo

from mcp_score.instruments import resolve_instrument

__all__ = ["ScoreManager"]

logger = logging.getLogger(__name__)

# Map barline type names to music21 barline types.
_BARLINE_TYPES: dict[str, str] = {
    "double": "double",
    "final": "final",
    "repeat-start": "start-repeat",
    "repeat-end": "end-repeat",
    "thin-thin": "double",
    "thin-thick": "final",
}

# Map duration names to music21 quarterLength values.
_DURATION_MAP: dict[str, float] = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "8th": 0.5,
    "16th": 0.25,
    "32nd": 0.125,
    "dotted-whole": 6.0,
    "dotted-half": 3.0,
    "dotted-quarter": 1.5,
    "dotted-eighth": 0.75,
    "dotted-8th": 0.75,
}


def _parse_key_signature(key_string: str) -> key.Key:
    """Parse a human-friendly key signature string.

    Examples: "C major", "Bb major", "F# minor", "Ab major", "D minor"
    """
    parts = key_string.strip().split()
    if len(parts) != 2:  # noqa: PLR2004
        msg = (
            f"Invalid key signature: '{key_string}'. "
            "Expected format: 'C major', 'Bb minor', etc."
        )
        raise ValueError(msg)

    tonic_raw, mode_raw = parts[0], parts[1].lower()

    # Convert flats: "Bb" -> "B-", "Ab" -> "A-", "Eb" -> "E-"
    # But not "B" alone (which is B natural).
    if len(tonic_raw) >= 2 and tonic_raw[1] == "b" and tonic_raw[0] != "b":
        tonic = tonic_raw[0].upper() + "-" + tonic_raw[2:]
    else:
        tonic = tonic_raw

    if mode_raw == "minor":
        tonic = tonic.lower()
    elif mode_raw != "major":
        msg = f"Invalid mode: '{mode_raw}'. Expected 'major' or 'minor'."
        raise ValueError(msg)

    return key.Key(tonic)


def _parse_time_signature(time_string: str) -> meter.TimeSignature:  # pyright: ignore[reportPrivateImportUsage]
    """Parse a time signature string like '4/4', '3/4', '6/8'."""
    if not re.match(r"^\d+/\d+$", time_string):
        msg = (
            f"Invalid time signature: '{time_string}'. "
            "Expected format: '4/4', '3/4', etc."
        )
        raise ValueError(msg)
    return meter.TimeSignature(time_string)  # pyright: ignore[reportPrivateImportUsage]


def _parse_pitch(pitch_string: str) -> str:
    """Normalize a pitch string for music21.

    Converts: "Bb4" -> "B-4", "F#3" -> "F#3", "C5" -> "C5"
    """
    # Replace 'b' (flat) with '-' when it follows a note letter.
    # Careful: "B4" is B natural, "Bb4" is B-flat.
    normalized = re.sub(r"(?<=[A-Ga-g])b(?=\d)", "-", pitch_string)
    return normalized


def _parse_duration(duration_string: str) -> float:
    """Parse a duration name to a quarterLength value."""
    quarter_length = _DURATION_MAP.get(duration_string.lower())
    if quarter_length is None:
        available = ", ".join(sorted(_DURATION_MAP.keys()))
        msg = f"Unknown duration: '{duration_string}'. Available: {available}"
        raise ValueError(msg)
    return quarter_length


class ScoreManager:
    """Manages the in-memory score being constructed.

    Holds a music21 Score object and provides methods for building
    and modifying it. MCP tools are thin wrappers around these methods.
    """

    def __init__(self) -> None:
        self._score: stream.Score | None = None

    @property
    def has_score(self) -> bool:
        """Whether a score is currently loaded."""
        return self._score is not None

    def _require_score(self) -> stream.Score:
        """Return the current score or raise."""
        if self._score is None:
            msg = "No score loaded. Use create_score first."
            raise RuntimeError(msg)
        return self._score

    def _find_part(self, part_index_or_name: str) -> stream.Part:
        """Find a part by index (0-based) or by name (case-insensitive)."""
        score = self._require_score()
        parts = list(score.parts)

        # Try numeric index first.
        try:
            index = int(part_index_or_name)
            if 0 <= index < len(parts):
                return parts[index]
            msg = f"Part index {index} out of range (0-{len(parts) - 1})."
            raise IndexError(msg)
        except ValueError:
            pass

        # Search by name (case-insensitive, partial match).
        search = part_index_or_name.lower()
        for part in parts:
            part_name = (part.partName or "").lower()
            if search == part_name or search in part_name:
                return part

        available = [p.partName or f"Part {i}" for i, p in enumerate(parts)]
        msg = f"Part '{part_index_or_name}' not found. Available: {available}"
        raise ValueError(msg)

    def _get_measure(self, part: stream.Part, measure_number: int) -> stream.Measure:
        """Get a specific measure from a part (1-indexed)."""
        result = part.measure(measure_number)  # pyright: ignore[reportUnknownMemberType]
        if not isinstance(result, stream.Measure):
            msg = f"Measure {measure_number} not found in part '{part.partName}'."
            raise ValueError(msg)
        return result

    def create_score(
        self,
        title: str,
        instruments: list[str],
        key_signature: str = "C major",
        time_signature: str = "4/4",
        tempo_bpm: int = 120,
        num_measures: int = 32,
    ) -> dict[str, Any]:
        """Create a new score, replacing any existing one."""
        try:
            key_sig = _parse_key_signature(key_signature)
            time_sig = _parse_time_signature(time_signature)
        except ValueError as exc:
            return {"error": str(exc)}

        if not instruments:
            return {"error": "At least one instrument is required."}

        score = stream.Score()
        score.metadata = stream.Score().metadata
        if score.metadata is not None:
            score.metadata.title = title

        # Resolve instruments and create parts.
        part_names: list[str] = []
        for instrument_name in instruments:
            try:
                inst = resolve_instrument(instrument_name)
            except ValueError as exc:
                return {"error": str(exc)}

            part = stream.Part()
            part.partName = inst.partName
            part.insert(0, inst)

            # Create measures with rests.
            for measure_num in range(1, num_measures + 1):
                measure = stream.Measure(number=measure_num)
                if measure_num == 1:
                    measure.insert(0.0, key_sig)
                    measure.insert(0.0, time_sig)
                whole_rest = note.Rest()
                whole_rest.quarterLength = time_sig.barDuration.quarterLength
                measure.append(whole_rest)
                part.append(measure)

            score.insert(0, part)
            part_names.append(inst.partName or instrument_name)

        # Add tempo to the first measure of the first part.
        first_part = list(score.parts)[0]
        first_measure = first_part.measure(1)
        if first_measure is not None:
            tempo_mark = tempo.MetronomeMark(number=tempo_bpm)
            first_measure.insert(0.0, tempo_mark)

        self._score = score
        logger.info("Created score '%s' with %d parts", title, len(instruments))

        return {
            "success": True,
            "message": f"Created '{title}' with {len(instruments)} parts, "
            f"{num_measures} measures, {key_signature}, {time_signature}, "
            f"{tempo_bpm} BPM.",
            "parts": part_names,
            "num_measures": num_measures,
        }

    def add_rehearsal_mark(self, measure: int, label: str) -> dict[str, Any]:
        """Add a rehearsal mark at the specified measure."""
        try:
            score = self._require_score()
        except RuntimeError as exc:
            return {"error": str(exc)}

        first_part = list(score.parts)[0]
        try:
            target_measure = self._get_measure(first_part, measure)
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

        mark = expressions.RehearsalMark(label)
        target_measure.insert(0.0, mark)

        logger.info("Added rehearsal mark '%s' at measure %d", label, measure)
        return {
            "success": True,
            "message": f"Rehearsal mark '{label}' added at measure {measure}.",
        }

    def set_barline(self, measure: int, barline_type: str) -> dict[str, Any]:
        """Set a barline type at the end of the specified measure."""
        try:
            score = self._require_score()
        except RuntimeError as exc:
            return {"error": str(exc)}

        music21_type = _BARLINE_TYPES.get(barline_type)
        if music21_type is None:
            available = ", ".join(sorted(_BARLINE_TYPES.keys()))
            return {
                "error": f"Unknown barline type: '{barline_type}'. "
                f"Available: {available}"
            }

        # Set barline on all parts for consistency.
        for part in score.parts:
            try:
                target_measure = self._get_measure(part, measure)
            except (ValueError, TypeError):
                continue
            target_measure.rightBarline = bar.Barline(music21_type)

        logger.info("Set %s barline at end of measure %d", barline_type, measure)
        return {
            "success": True,
            "message": f"Set '{barline_type}' barline at end of measure {measure}.",
        }

    def add_chord_symbol(
        self,
        part_index_or_name: str,
        measure: int,
        beat: float,
        symbol: str,
    ) -> dict[str, Any]:
        """Add a chord symbol at the specified position."""
        try:
            part = self._find_part(part_index_or_name)
        except (RuntimeError, ValueError, IndexError) as exc:
            return {"error": str(exc)}

        try:
            target_measure = self._get_measure(part, measure)
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

        # music21 offsets are 0-based; beat 1 = offset 0.0.
        offset = beat - 1.0
        chord_symbol = harmony.ChordSymbol(symbol)
        target_measure.insert(offset, chord_symbol)

        logger.info(
            "Added chord symbol '%s' at measure %d, beat %s", symbol, measure, beat
        )
        return {
            "success": True,
            "message": f"Chord symbol '{symbol}' added at measure {measure}, "
            f"beat {beat}.",
        }

    def add_tempo_marking(
        self,
        measure: int,
        bpm: int,
        text: str | None = None,
    ) -> dict[str, Any]:
        """Add a tempo marking at the specified measure."""
        try:
            score = self._require_score()
        except RuntimeError as exc:
            return {"error": str(exc)}

        first_part = list(score.parts)[0]
        try:
            target_measure = self._get_measure(first_part, measure)
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

        tempo_mark = tempo.MetronomeMark(number=bpm, text=text)
        target_measure.insert(0.0, tempo_mark)

        display = f"{bpm} BPM" if text is None else f"{text} ({bpm} BPM)"
        logger.info("Added tempo marking %s at measure %d", display, measure)
        return {
            "success": True,
            "message": f"Tempo marking {display} added at measure {measure}.",
        }

    def add_notes(
        self,
        part_index_or_name: str,
        measure: int,
        notes: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Add notes to a specific part and measure.

        Replaces any existing content (rests) in the measure.
        """
        try:
            part = self._find_part(part_index_or_name)
        except (RuntimeError, ValueError, IndexError) as exc:
            return {"error": str(exc)}

        try:
            target_measure = self._get_measure(part, measure)
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

        # Remove existing notes/rests.
        for element in list(target_measure.notesAndRests):
            target_measure.remove(element)

        note_count = 0
        current_offset = 0.0
        for note_dict in notes:
            pitch_str = note_dict.get("pitch", "")
            duration_str = note_dict.get("duration", "quarter")

            try:
                quarter_length = _parse_duration(duration_str)
            except ValueError as exc:
                return {"error": str(exc)}

            if pitch_str.lower() == "rest":
                rest = note.Rest()
                rest.quarterLength = quarter_length
                target_measure.insert(current_offset, rest)
            else:
                try:
                    parsed_pitch = _parse_pitch(pitch_str)
                    new_note = note.Note(parsed_pitch)
                    new_note.quarterLength = quarter_length
                    target_measure.insert(current_offset, new_note)
                except Exception as exc:  # noqa: BLE001
                    return {"error": f"Invalid pitch '{pitch_str}': {exc}"}

            current_offset += quarter_length
            note_count += 1

        logger.info(
            "Added %d notes to %s, measure %d",
            note_count,
            part.partName,
            measure,
        )
        return {
            "success": True,
            "message": f"Added {note_count} notes to '{part.partName}', "
            f"measure {measure}.",
        }

    def get_score_info(self) -> dict[str, Any]:
        """Get information about the current score."""
        try:
            score = self._require_score()
        except RuntimeError as exc:
            return {"error": str(exc)}

        parts_info: list[dict[str, Any]] = []
        for part_index, part in enumerate(score.parts):
            inst = part.getInstrument()
            parts_info.append(
                {
                    "index": part_index,
                    "name": part.partName or f"Part {part_index}",
                    "instrument": inst.instrumentName if inst else "Unknown",
                    "transposition": (
                        str(inst.transposition) if inst and inst.transposition else None
                    ),
                }
            )

        num_measures = 0
        if parts_info:
            first_part = list(score.parts)[0]
            num_measures = len(first_part.getElementsByClass(stream.Measure))

        title = ""
        if score.metadata is not None:
            title = score.metadata.title or ""

        return {
            "success": True,
            "title": title,
            "num_parts": len(parts_info),
            "num_measures": num_measures,
            "parts": parts_info,
        }

    def export_musicxml(self, filepath: str) -> dict[str, Any]:
        """Export the current score as MusicXML."""
        try:
            score = self._require_score()
        except RuntimeError as exc:
            return {"error": str(exc)}

        try:
            score.write("musicxml", fp=filepath)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Export failed: {exc}"}

        logger.info("Exported score to %s", filepath)
        return {
            "success": True,
            "message": f"Score exported to {filepath}.",
            "filepath": filepath,
        }

    def clear(self) -> dict[str, Any]:
        """Clear the current score."""
        self._score = None
        logger.info("Score cleared")
        return {"success": True, "message": "Score cleared."}
