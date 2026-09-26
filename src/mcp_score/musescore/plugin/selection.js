// Selection, transposition and undo.
.pragma library
.import "constants.js" as Constants
.import "score.js" as Score

/// Select all elements in the measure at the current cursor position.
function applySelectCurrentMeasure(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (!cursor.measure) {
        return { error: "No measure at current cursor position" };
    }

    var measureStart = cursor.measure.firstSegment.tick;
    var measureEnd = cursor.measure.lastSegment.tick + 1;
    plugin.curScore.selection.selectRange(measureStart, measureEnd, plugin.cursorStaff, plugin.cursorStaff + 1);

    return { result: { measure: plugin.cursorMeasure, staff: plugin.cursorStaff } };
}

function selectCurrentMeasure(plugin, params) {
    return Score.withUndoStep(plugin, "selectCurrentMeasure", function() { return applySelectCurrentMeasure(plugin, params); });
}

/// Select a range of measures and staves.
/// Params: { startMeasure, endMeasure, startStaff, endStaff }
/// Measures are 1-indexed (inclusive). Staves are 0-indexed (inclusive).
function applySelectCustomRange(plugin, params) {
    var startMeasure = Score.safeParseInt(params.startMeasure);
    var endMeasure = Score.safeParseInt(params.endMeasure);
    var startStaff = Score.safeParseInt(params.startStaff);
    var endStaff = Score.safeParseInt(params.endStaff);

    if (startMeasure === null || endMeasure === null ||
        startStaff === null || endStaff === null) {
        return { error: "Missing required parameters: startMeasure, endMeasure, startStaff, endStaff" };
    }

    var curScore = plugin.curScore;
    var totalMeasures = Score.countMeasures(plugin);
    if (startMeasure < 1 || startMeasure > totalMeasures ||
        endMeasure < 1 || endMeasure > totalMeasures ||
        startMeasure > endMeasure) {
        return { error: "Invalid measure range: " + startMeasure + "-" + endMeasure +
            " (score has " + totalMeasures + " measures)" };
    }
    if (startStaff < 0 || startStaff >= curScore.nstaves ||
        endStaff < 0 || endStaff >= curScore.nstaves ||
        startStaff > endStaff) {
        return { error: "Invalid staff range: " + startStaff + "-" + endStaff +
            " (score has " + curScore.nstaves + " staves)" };
    }

    // Find tick positions for the measure range.
    var cursor = curScore.newCursor();
    Score.advanceCursorToMeasure(cursor, startMeasure);
    var startTick = cursor.tick;
    for (var j = startMeasure; j <= endMeasure; j++) {
        cursor.nextMeasure();
    }
    var endTick = cursor.measure ? cursor.tick : curScore.lastSegment.tick + 1;

    // selectRange uses an exclusive end for staves.
    curScore.selection.selectRange(startTick, endTick, startStaff, endStaff + 1);

    return {
        result: {
            startMeasure: startMeasure,
            endMeasure: endMeasure,
            startStaff: startStaff,
            endStaff: endStaff
        }
    };
}

function selectCustomRange(plugin, params) {
    return Score.withUndoStep(plugin, "selectCustomRange", function() { return applySelectCustomRange(plugin, params); });
}

/// Transpose the notes in the current selection by a number of semitones.
/// Params: { semitones }
/// Requires an active selection (use selectCurrentMeasure or selectCustomRange first).
///
/// MuseScore 4's plugin API has no transpose call, so each selected
/// note is shifted directly, with its spelling moved by the
/// conventional interval. Key signatures and chord symbols are not
/// transposed.
function applyTranspose(plugin, params) {
    if (params.semitones === undefined) {
        return { error: "Missing required parameter: semitones" };
    }
    var semitones = Score.safeParseInt(params.semitones);
    if (semitones === null) {
        return { error: "Invalid value for semitones: " + params.semitones };
    }
    var selection = plugin.curScore.selection;
    if (!selection || !selection.elements || selection.elements.length === 0) {
        return { error: "No active selection. Use selectCurrentMeasure or selectCustomRange first." };
    }

    var elements = selection.elements;
    var notes = [];
    for (var i = 0; i < elements.length; i++) {
        if (elements[i].type === plugin.Element.NOTE) {
            notes.push(elements[i]);
        }
    }
    if (notes.length === 0) {
        return { error: "The selection contains no notes" };
    }

    // Validate every target pitch before changing anything.
    for (var v = 0; v < notes.length; v++) {
        var target = notes[v].pitch + semitones;
        if (target < Constants.minMidiPitch || target > Constants.maxMidiPitch) {
            return { error: "Transposition would move a note to MIDI pitch " + target +
                ", outside " + Constants.minMidiPitch + "-" + Constants.maxMidiPitch };
        }
    }

    var tpcDelta = Constants.semitoneToTpcDelta[((semitones % 12) + 12) % 12];
    for (var n = 0; n < notes.length; n++) {
        var note = notes[n];
        note.pitch = note.pitch + semitones;
        note.tpc1 = Score.respellTpc(note.tpc1 + tpcDelta);
        note.tpc2 = Score.respellTpc(note.tpc2 + tpcDelta);
    }

    return { result: { semitones: semitones, notes: notes.length } };
}

function transpose(plugin, params) {
    return Score.withUndoStep(plugin, "transpose", function() { return applyTranspose(plugin, params); });
}

/// Undo the last action.
function undo(plugin, params) {
    var scoreErr = Score.requireScore(plugin);
    if (scoreErr) return scoreErr;

    plugin.cmd(Score.undoActionCode(plugin));

    // Clamp cursor to valid bounds -- undo may have changed the score
    // structure (removed measures, changed staves).
    var totalMeasures = Score.countMeasures(plugin);
    if (totalMeasures > 0 && plugin.cursorMeasure > totalMeasures) {
        plugin.cursorMeasure = totalMeasures;
    }
    var staffCount = plugin.curScore.nstaves;
    if (staffCount > 0 && plugin.cursorStaff >= staffCount) {
        plugin.cursorStaff = staffCount - 1;
    }

    return { result: { measure: plugin.cursorMeasure, staff: plugin.cursorStaff } };
}
