// Lookup tables and bounds shared by the bridge plugin's modules.
.pragma library

// MuseScore internal tick counts (from fraction.h).
var ticksPerWholeNote = 1920;
var secondsPerMinute = 60.0;

// Key signature bounds (circle of fifths).
var minFifths = -7;
var maxFifths = 7;

// Barline type string -> MuseScore enum value.
var barlineTypes = {
    "normal":         1,
    "double":         2,
    "startRepeat":    4,
    "endRepeat":      8,
    "endStartRepeat": 16,
    "final":          32,
    "dashed":         64,
    "dotted":         128,
    "tick":           256,
    "short":          512
};

// Dynamic marking -> MIDI velocity.
var dynamicVelocities = {
    "pppp": 10,  "ppp": 25,  "pp": 36,  "p": 49,   "mp": 64,
    "mf": 80,    "f": 96,    "ff": 112,  "fff": 120, "ffff": 127,
    "fp": 96,    "sfz": 112, "sffz": 120, "sfp": 112, "rfz": 112,
    "fz": 112
};

// Semitone interval (0-11, upward) -> change in tonal pitch class.
// Gives the conventional spelling for each interval: a minor second
// up spells C as Db (tpc -5), a major second up as D (tpc +2), and
// so on. Downward intervals use the same table via modulo 12.
var semitoneToTpcDelta = [0, -5, 2, -3, 4, -1, 6, 1, -4, 3, -2, 5];

// Tonal pitch class bounds (Fbb .. B##) and the enharmonic step.
var minTpc = -1;
var maxTpc = 33;
var tpcEnharmonicStep = 12;

// MIDI pitch bounds.
var minMidiPitch = 0;
var maxMidiPitch = 127;

// Tracks per staff in MuseScore (four voices).
var voicesPerStaff = 4;
