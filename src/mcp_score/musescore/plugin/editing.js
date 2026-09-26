// Commands that change the score.
//
// Each command has an `apply*` function that validates its parameters
// and mutates the score without opening an undo step, and a plain
// function that runs it inside one undo step. processSequence runs
// several `apply*` calls inside a single step so the batch undoes
// together.
.pragma library
.import MuseScore 3.0 as MS
.import "constants.js" as Constants
.import "score.js" as Score

/// Add a note at the current cursor position.
/// Params: { pitch, duration?: { numerator, denominator }, advanceCursorAfterAction?: bool }
function applyAddNote(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.pitch === undefined) {
        return { error: "Missing required parameter: pitch" };
    }
    var pitch = Score.safeParseInt(params.pitch);
    if (pitch === null) {
        return { error: "Invalid value for pitch: " + params.pitch };
    }
    if (pitch < Constants.minMidiPitch || pitch > Constants.maxMidiPitch) {
        return { error: "pitch must be between " + Constants.minMidiPitch + " and "
            + Constants.maxMidiPitch + ", got: " + pitch };
    }

    var numerator = 1;
    var denominator = 4;
    if (params.duration) {
        if (params.duration.numerator !== undefined) {
            numerator = Score.safeParseInt(params.duration.numerator);
            if (numerator === null) return { error: "Invalid duration numerator" };
        }
        if (params.duration.denominator !== undefined) {
            denominator = Score.safeParseInt(params.duration.denominator);
            if (denominator === null) return { error: "Invalid duration denominator" };
        }
    }
    var advance = (params.advanceCursorAfterAction !== false);

    cursor.setDuration(numerator, denominator);
    cursor.addNote(pitch);

    if (advance) {
        plugin.cursorMeasure = Score.measureNumberAtTick(plugin, cursor.tick);
    }

    return {
        result: {
            pitch: pitch,
            duration: { numerator: numerator, denominator: denominator },
            measure: plugin.cursorMeasure,
            staff: plugin.cursorStaff
        }
    };
}

function addNote(plugin, params) {
    return Score.withUndoStep(plugin, "addNote", function() { return applyAddNote(plugin, params); });
}

/// Add a rehearsal mark at the current cursor position.
/// Params: { text }
function applyAddRehearsalMark(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.text === undefined || params.text === "") {
        return { error: "Missing required parameter: text" };
    }
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var rehearsalMark = plugin.newElement(MS.Element.REHEARSAL_MARK);
    rehearsalMark.text = params.text;
    cursor.add(rehearsalMark);

    return { result: { text: params.text, measure: plugin.cursorMeasure } };
}

function addRehearsalMark(plugin, params) {
    return Score.withUndoStep(plugin, "addRehearsalMark", function() { return applyAddRehearsalMark(plugin, params); });
}

/// Set the barline at the end of the measure at the cursor position.
/// Params: { type }
///
/// MuseScore 4 rejects bar lines inserted through Cursor.add (it
/// crashes), so this changes the measure's existing end bar line on
/// every staff instead. Repeats are measure flags in MuseScore, so
/// the repeat types set those.
function applySetBarline(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.type === undefined) {
        return { error: "Missing required parameter: type" };
    }
    var barlineType = Score.barlineTypeFromString(params.type);
    if (barlineType === null) {
        return { error: "Unknown barline type: " + params.type +
            ". Valid types: " + Object.keys(Constants.barlineTypes).join(", ") };
    }
    var measure = cursor.measure;
    if (!measure) {
        return { error: "No valid measure at cursor position" };
    }

    if (params.type === "startRepeat") {
        measure.repeatStart = true;
        return { result: { type: params.type, measure: plugin.cursorMeasure } };
    }
    if (params.type === "endStartRepeat") {
        var next = measure.nextMeasure;
        if (!next) {
            return { error: "endStartRepeat needs a following measure to start the repeat in" };
        }
        measure.repeatEnd = true;
        next.repeatStart = true;
        return { result: { type: params.type, measure: plugin.cursorMeasure } };
    }
    if (params.type === "endRepeat") {
        measure.repeatEnd = true;
        return { result: { type: params.type, measure: plugin.cursorMeasure } };
    }

    // A plain type replaces any end repeat on this measure.
    measure.repeatEnd = false;
    var endSegment = measure.lastSegment;
    var changed = 0;
    for (var staff = 0; staff < plugin.curScore.nstaves; staff++) {
        var element = endSegment ? endSegment.elementAt(staff * Constants.voicesPerStaff) : null;
        if (element && element.type === MS.Element.BAR_LINE) {
            element.barlineType = barlineType;
            changed++;
        }
    }
    if (changed === 0) {
        return { error: "No end bar line found for measure " + plugin.cursorMeasure };
    }

    return { result: { type: params.type, measure: plugin.cursorMeasure } };
}

function setBarline(plugin, params) {
    return Score.withUndoStep(plugin, "setBarline", function() { return applySetBarline(plugin, params); });
}

/// Set the key signature at the current cursor position.
/// Params: { fifths } (-7 to 7 on the circle of fifths)
function applySetKeySignature(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.fifths === undefined) {
        return { error: "Missing required parameter: fifths" };
    }
    var fifths = Score.safeParseInt(params.fifths);
    if (fifths === null) {
        return { error: "Invalid value for fifths: " + params.fifths };
    }
    if (fifths < Constants.minFifths || fifths > Constants.maxFifths) {
        return { error: "fifths must be between " + Constants.minFifths + " and "
            + Constants.maxFifths + ", got: " + fifths };
    }
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var keySig = plugin.newElement(MS.Element.KEYSIG);
    keySig.key = fifths;
    cursor.add(keySig);

    return { result: { fifths: fifths, measure: plugin.cursorMeasure } };
}

function setKeySignature(plugin, params) {
    return Score.withUndoStep(plugin, "setKeySignature", function() { return applySetKeySignature(plugin, params); });
}

/// Set the time signature at the current cursor position.
/// Params: { numerator, denominator }
function applySetTimeSignature(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.numerator === undefined || params.denominator === undefined) {
        return { error: "Missing required parameters: numerator and denominator" };
    }
    var numerator = Score.safeParseInt(params.numerator);
    var denominator = Score.safeParseInt(params.denominator);
    if (numerator === null || denominator === null) {
        return { error: "Invalid time signature values" };
    }
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var timeSig = plugin.newElement(MS.Element.TIMESIG);
    timeSig.timesig = plugin.fraction(numerator, denominator);
    cursor.add(timeSig);

    return { result: { numerator: numerator, denominator: denominator, measure: plugin.cursorMeasure } };
}

function setTimeSignature(plugin, params) {
    return Score.withUndoStep(plugin, "setTimeSignature", function() { return applySetTimeSignature(plugin, params); });
}

/// Set a tempo marking at the current cursor position.
/// Params: { bpm, text? }
function applySetTempo(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.bpm === undefined) {
        return { error: "Missing required parameter: bpm" };
    }
    var bpm = Score.safeParseInt(params.bpm);
    if (bpm === null) {
        return { error: "Invalid value for bpm: " + params.bpm };
    }
    var displayText = params.text || ("♩ = " + bpm);
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var tempo = plugin.newElement(MS.Element.TEMPO_TEXT);
    tempo.text = displayText;
    tempo.tempo = bpm / Constants.secondsPerMinute;
    tempo.followText = false;
    cursor.add(tempo);

    return { result: { bpm: bpm, text: displayText, measure: plugin.cursorMeasure } };
}

function setTempo(plugin, params) {
    return Score.withUndoStep(plugin, "setTempo", function() { return applySetTempo(plugin, params); });
}

/// Add a chord symbol at the current cursor position.
/// Params: { text }
///
/// The text is set after the element is in the score: MuseScore 4
/// crashes when a chord symbol is parsed before it has a parent.
function applyAddChordSymbol(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.text === undefined || params.text === "") {
        return { error: "Missing required parameter: text" };
    }
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var harmony = plugin.newElement(MS.Element.HARMONY);
    cursor.add(harmony);
    harmony.text = params.text;

    return { result: { text: params.text, measure: plugin.cursorMeasure } };
}

function addChordSymbol(plugin, params) {
    return Score.withUndoStep(plugin, "addChordSymbol", function() { return applyAddChordSymbol(plugin, params); });
}

/// Add a dynamic marking at the current cursor position.
/// Params: { type }
function applyAddDynamic(plugin, params) {
    var req = Score.requireCursor(plugin);
    if (req.error) return req.error;
    var cursor = req.cursor;

    if (params.type === undefined || params.type === "") {
        return { error: "Missing required parameter: type" };
    }
    if (!cursor.segment) {
        return { error: "No valid segment at cursor position" };
    }

    var dynamic = plugin.newElement(MS.Element.DYNAMIC);
    dynamic.text = params.type;
    if (Constants.dynamicVelocities[params.type] !== undefined) {
        dynamic.velocity = Constants.dynamicVelocities[params.type];
    }
    cursor.add(dynamic);

    return { result: { type: params.type, measure: plugin.cursorMeasure } };
}

function addDynamic(plugin, params) {
    return Score.withUndoStep(plugin, "addDynamic", function() { return applyAddDynamic(plugin, params); });
}

/// Append empty measures to the end of the score.
/// Params: { count }
function applyAppendMeasures(plugin, params) {
    if (params.count === undefined) {
        return { error: "Missing required parameter: count" };
    }
    var count = Score.safeParseInt(params.count);
    if (count === null || count < 1) {
        return { error: "count must be at least 1, got: " + count };
    }

    plugin.curScore.appendMeasures(count);

    return { result: { count: count, totalMeasures: Score.countMeasures(plugin) } };
}

function appendMeasures(plugin, params) {
    return Score.withUndoStep(plugin, "appendMeasures", function() { return applyAppendMeasures(plugin, params); });
}
