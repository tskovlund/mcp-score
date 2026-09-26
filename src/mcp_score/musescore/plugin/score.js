// Working with the open score: guards, cursor positioning, undo steps
// and the helpers every command module shares.
//
// Every function takes the plugin (the MuseScore QML item) explicitly:
// it holds the logical cursor position and is the way into MuseScore's
// plugin API (curScore, newElement, cmd, ...).
.pragma library
.import MuseScore 3.0 as MS
.import "constants.js" as Constants

// ── Guards ────────────────────────────────────────────────────────────

/// Returns an error object if no score is open, or null if OK.
function requireScore(plugin) {
    if (!plugin.curScore) {
        return { error: "No score is currently open" };
    }
    return null;
}

/// Returns a positioned cursor, or an error object if it cannot be created.
function requireCursor(plugin) {
    var scoreErr = requireScore(plugin);
    if (scoreErr) return { cursor: null, error: scoreErr };

    var cursor = positionedCursor(plugin);
    if (!cursor) return { cursor: null, error: { error: "Could not position cursor" } };

    return { cursor: cursor, error: null };
}

// ── Cursor positioning ────────────────────────────────────────────────

/// Create a MuseScore Cursor at the plugin's current logical position.
function positionedCursor(plugin) {
    if (!plugin.curScore) return null;
    var cursor = plugin.curScore.newCursor();
    cursor.staffIdx = plugin.cursorStaff;
    cursor.voice = plugin.cursorVoice;
    cursor.rewind(MS.Cursor.SCORE_START);

    for (var i = 1; i < plugin.cursorMeasure; i++) {
        cursor.nextMeasure();
    }
    return cursor;
}

/// Navigate a raw cursor to a specific 1-indexed measure number.
function advanceCursorToMeasure(cursor, measureNumber) {
    cursor.rewind(MS.Cursor.SCORE_START);
    for (var i = 1; i < measureNumber; i++) {
        cursor.nextMeasure();
    }
}

/// Count the total number of measures in the score.
function countMeasures(plugin) {
    if (!plugin.curScore) return 0;
    var cursor = plugin.curScore.newCursor();
    cursor.rewind(MS.Cursor.SCORE_START);
    var count = 0;
    while (cursor.measure) {
        count++;
        cursor.nextMeasure();
    }
    return count;
}

/// Get the 1-indexed measure number for a given tick position.
function measureNumberAtTick(plugin, tick) {
    if (!plugin.curScore) return 0;
    var cursor = plugin.curScore.newCursor();
    cursor.rewind(MS.Cursor.SCORE_START);
    var measureNumber = 1;
    while (cursor.measure) {
        var measureStart = cursor.tick;
        cursor.nextMeasure();
        var measureEnd = cursor.measure ? cursor.tick : Infinity;
        if (tick >= measureStart && tick < measureEnd) {
            return measureNumber;
        }
        measureNumber++;
    }
    return measureNumber;
}

// ── Undo steps ────────────────────────────────────────────────────────

/// Run `fn` inside one MuseScore undo step named `name`.
/// The step is committed when `fn` returns a result and rolled back
/// when it returns an error or throws, so a failed command never
/// leaves partial changes in the score.
function withUndoStep(plugin, name, fn) {
    var scoreErr = requireScore(plugin);
    if (scoreErr) return scoreErr;

    plugin.curScore.startCmd(name);
    var response;
    try {
        response = fn();
    } catch (e) {
        plugin.curScore.endCmd(true);
        throw e;
    }
    plugin.curScore.endCmd(response.error !== undefined);
    return response;
}

/// Action code that undoes the last step in the running MuseScore.
/// MuseScore 4.7 moved notation actions to query-style codes; the
/// plain "undo" code is what 4.4-4.6 register.
function undoActionCode(plugin) {
    var queryStyleActions = plugin.mscoreMajorVersion > 4
        || (plugin.mscoreMajorVersion === 4 && plugin.mscoreMinorVersion >= 7);
    return queryStyleActions ? "action://notation/undo" : "undo";
}

// ── Values ────────────────────────────────────────────────────────────

/// Map a barline type string to the MuseScore enum value, or null.
function barlineTypeFromString(typeString) {
    var value = Constants.barlineTypes[typeString];
    return (value !== undefined) ? value : null;
}

/// Parse a value to integer, returning null if the result is NaN.
function safeParseInt(value) {
    var parsed = parseInt(value);
    return isNaN(parsed) ? null : parsed;
}

/// Bring a tonal pitch class back into range by respelling it
/// enharmonically (e.g. B## becomes C#).
function respellTpc(tpc) {
    while (tpc > Constants.maxTpc) tpc -= Constants.tpcEnharmonicStep;
    while (tpc < Constants.minTpc) tpc += Constants.tpcEnharmonicStep;
    return tpc;
}

/// Describe a score element as a plain object for JSON serialization.
function describeElement(element) {
    if (!element) return null;

    var info = { type: element.type };

    if (element.type === MS.Element.CHORD) {
        var notes = [];
        for (var i = 0; i < element.notes.length; i++) {
            var note = element.notes[i];
            notes.push({
                pitch: note.pitch,
                tpc: note.tpc,
                name: note.noteName || null
            });
        }
        info.notes = notes;
        info.duration = {
            numerator: element.duration.numerator,
            denominator: element.duration.denominator
        };
    } else if (element.type === MS.Element.REST) {
        info.duration = {
            numerator: element.duration.numerator,
            denominator: element.duration.denominator
        };
    } else if (element.type === MS.Element.NOTE) {
        info.pitch = element.pitch;
        info.tpc = element.tpc;
        info.name = element.noteName || null;
    }

    return info;
}
