// Read-only commands and navigation: nothing here changes the score.
.pragma library
.import MuseScore 3.0 as MS
.import "constants.js" as Constants
.import "score.js" as Score

function ping(plugin, params) {
    return { result: "pong" };
}

/// Return metadata about the currently open score.
function getScore(plugin, params) {
    var scoreErr = Score.requireScore(plugin);
    if (scoreErr) return scoreErr;
    var curScore = plugin.curScore;

    var parts = [];
    for (var i = 0; i < curScore.parts.length; i++) {
        var part = curScore.parts[i];
        parts.push({
            name: part.partName,
            startStaff: part.startStaff,
            endStaff: part.endStaff
        });
    }

    var cursor = curScore.newCursor();
    cursor.rewind(MS.Cursor.SCORE_START);

    var keySig = (cursor.keySignature !== undefined) ? cursor.keySignature : null;

    var timeSig = null;
    if (cursor.timeSignature) {
        timeSig = {
            numerator: cursor.timeSignature.numerator,
            denominator: cursor.timeSignature.denominator
        };
    }

    return {
        result: {
            title: curScore.title || "",
            partCount: parts.length,
            parts: parts,
            measureCount: Score.countMeasures(plugin),
            keySignature: keySig,
            timeSignature: timeSig
        }
    };
}

/// Return the current logical cursor position and the element there.
function getCursorInfo(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    var elementInfo = cursor.element ? Score.describeElement(cursor.element) : null;

    var beat = null;
    if (cursor.measure && cursor.timeSignature) {
        var measureStartTick = cursor.measure.firstSegment.tick;
        var ticksPerBeat = Constants.ticksPerWholeNote / cursor.timeSignature.denominator;
        beat = Math.floor((cursor.tick - measureStartTick) / ticksPerBeat) + 1;
    }

    return {
        result: {
            measure: plugin.cursorMeasure,
            staff: plugin.cursorStaff,
            voice: plugin.cursorVoice,
            beat: beat,
            tick: cursor.tick,
            element: elementInfo
        }
    };
}

/// Move the logical cursor to the specified 1-indexed measure.
function goToMeasure(plugin, params) {
    var scoreErr = Score.requireScore(plugin);
    if (scoreErr) return scoreErr;

    if (params.measure === undefined) {
        return { error: "Missing required parameter: measure" };
    }

    var measureNumber = Score.safeParseInt(params.measure);
    if (measureNumber === null) {
        return { error: "Invalid value for measure: " + params.measure };
    }
    var totalMeasures = Score.countMeasures(plugin);

    if (measureNumber < 1 || measureNumber > totalMeasures) {
        return { error: "Measure " + measureNumber + " out of range (1-" + totalMeasures + ")" };
    }

    plugin.cursorMeasure = measureNumber;
    return { result: { measure: plugin.cursorMeasure, staff: plugin.cursorStaff } };
}

/// Move the logical cursor to the specified 0-indexed staff.
function goToStaff(plugin, params) {
    var scoreErr = Score.requireScore(plugin);
    if (scoreErr) return scoreErr;

    if (params.staff === undefined) {
        return { error: "Missing required parameter: staff" };
    }

    var staffIndex = Score.safeParseInt(params.staff);
    if (staffIndex === null) {
        return { error: "Invalid value for staff: " + params.staff };
    }
    var staffCount = plugin.curScore.nstaves;
    if (staffIndex < 0 || staffIndex >= staffCount) {
        return { error: "Staff " + staffIndex + " out of range (0-" + (staffCount - 1) + ")" };
    }

    plugin.cursorStaff = staffIndex;
    return { result: { measure: plugin.cursorMeasure, staff: plugin.cursorStaff } };
}
