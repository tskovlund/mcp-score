// processSequence: several commands in one undo step.
.pragma library
.import "score.js" as Score
.import "reading.js" as Reading
.import "editing.js" as Editing
.import "selection.js" as Selection

// What each step runs. Editing steps use the `apply*` form so the whole
// sequence shares the caller's undo step.
var steps = {
    "ping":                 Reading.ping,
    "goToMeasure":          Reading.goToMeasure,
    "goToStaff":            Reading.goToStaff,
    "addNote":              Editing.applyAddNote,
    "addRehearsalMark":     Editing.applyAddRehearsalMark,
    "setBarline":           Editing.applySetBarline,
    "setKeySignature":      Editing.applySetKeySignature,
    "setTimeSignature":     Editing.applySetTimeSignature,
    "setTempo":             Editing.applySetTempo,
    "addChordSymbol":       Editing.applyAddChordSymbol,
    "addDynamic":           Editing.applyAddDynamic,
    "appendMeasures":       Editing.applyAppendMeasures,
    "selectCurrentMeasure": Selection.applySelectCurrentMeasure,
    "selectCustomRange":    Selection.applySelectCustomRange,
    "transpose":            Selection.applyTranspose
};

/// Execute one step inside the caller's undo step.
function executeStep(plugin, action, params) {
    var step = steps[action];
    if (!step) {
        return { error: "Unknown action in sequence: " + action };
    }
    return step(plugin, params);
}

/// Execute multiple actions in a single undo step.
/// If any action fails, the score and the cursor are restored to
/// their state before the sequence.
///
/// Params: { sequence: [{ action, params }, ...] }
function processSequence(plugin, params) {
    var scoreErr = Score.requireScore(plugin);
    if (scoreErr) return scoreErr;

    if (!params.sequence || !Array.isArray(params.sequence)) {
        return { error: "Missing required parameter: sequence (array of {action, params})" };
    }
    var sequence = params.sequence;
    if (sequence.length === 0) {
        return { result: { results: [], count: 0 } };
    }

    var savedMeasure = plugin.cursorMeasure;
    var savedStaff = plugin.cursorStaff;

    var response = Score.withUndoStep(plugin, "processSequence", function() {
        var results = [];
        for (var i = 0; i < sequence.length; i++) {
            var step = sequence[i];
            var action = step.action;
            if (!action) {
                return { error: "Step " + i + " is missing 'action' field", failedIndex: i, results: results };
            }

            var stepResult;
            try {
                stepResult = executeStep(plugin, action, step.params || {});
            } catch (e) {
                stepResult = { error: e.message || String(e) };
            }
            if (stepResult.error) {
                return {
                    error: "Step " + i + " (" + action + ") failed: " + stepResult.error,
                    failedAction: action,
                    failedIndex: i,
                    results: results
                };
            }
            results.push(stepResult.result);
        }
        return { result: { results: results, count: results.length } };
    });

    if (response.error !== undefined) {
        plugin.cursorMeasure = savedMeasure;
        plugin.cursorStaff = savedStaff;
    }
    return response;
}
