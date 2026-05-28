/* Harmonysplorer engine — pure-JS port of main.py
 *
 * Conventions (jazz):
 *   "7"     → minor 7th added to triad (dominant on major, m7 on minor, etc.)
 *   "maj7"  → major 7th
 *   "o" / "dim" → diminished triad/7th
 *   "h"     → half-diminished
 *   "+" / "aug" → augmented
 *   Colon notation: "I:2" = I chord with default inversion 2 (5th in bass)
 *   Slash: "V7/ii" = V7 of ii (secondary dominant)
 *
 * Exposes window.Engine = { getChords, parseChord, voiceLead, exportMidi }.
 */
(function (global) {
  'use strict';

  // ───────────────────────────────────────────────
  // Constants
  // ───────────────────────────────────────────────

  const FLAT_NAMES  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'];
  const SHARP_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];

  const KEY_SIGS = {
    'C':0,'G':1,'D':2,'A':3,'E':4,'B':5,'F#':6,'C#':7,
    'F':-1,'Bb':-2,'Eb':-3,'Ab':-4,'Db':-5,'Gb':-6,'Cb':-7,
  };

  const NOTE_TO_PC = {
    'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'E#':5,'Fb':4,
    'F':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,
    'B':11,'B#':0,'Cb':11,
  };

  const DEGREE_SEMITONES = {'I':0,'II':2,'III':4,'IV':5,'V':7,'VI':9,'VII':11};

  const INTERVALS = {
    'maj':     [0,4,7],
    'min':     [0,3,7],
    'dim':     [0,3,6],
    'aug':     [0,4,8],
    'dom7':    [0,4,7,10],
    'maj7':    [0,4,7,11],
    'm7':      [0,3,7,10],
    'mmaj7':   [0,3,7,11],
    'halfdim': [0,3,6,10],
    'dim7':    [0,3,6,9],
    'aug7':    [0,4,8,10],
    'dom9':    [0,4,10,14],
    'maj9':    [0,4,11,14],
    'm9':      [0,3,10,14],
    'sus4':    [0,5,7],
    'sus2':    [0,2,7],
    'sus47':   [0,5,7,10],
  };

  const QUALITY_NAMES = {
    'maj':'major triad','min':'minor triad','dim':'diminished triad','aug':'augmented triad',
    'dom7':'dominant 7th','maj7':'major 7th','m7':'minor 7th',
    'mmaj7':'minor-major 7th','halfdim':'half-diminished 7th','dim7':'diminished 7th',
    'aug7':'augmented 7th','dom9':'dominant 9th','maj9':'major 9th','m9':'minor 9th',
    'sus4':'suspended 4th','sus2':'suspended 2nd','sus47':'sus4 dom7',
  };

  // Roman numeral regex — groups: accidental | degree | triad-mod | extension | figured-bass | secondary
  const RN_RE = new RegExp(
    '^(bb|b|##|#)?' +
    '(VII|VI|IV|III|II|I|vii|vi|iv|iii|ii|i|V|v)' +
    '(\\+|aug|h|o)?' +
    '(maj7|maj9|mMaj7|m7b5|m7|sus4(?:7)?|sus2|add9|9|7)?' +
    '(64|65|43|42|6)?' +
    '(?:/(.+))?$'
  );

  const FUNCTION_MAP = {
    "major": {
      "tonic":       ["I","Imaj7","I:1","iii","iii7","vi","vi7"],
      "predominant": ["ii","ii7","ii:1","IV","IVmaj7","IV:1"],
      "dominant":    ["I:2","V","V7","V7:1","V7:3","V9","viio","viih7","V/V","V7/V"],
      "borrowed":    ["bVI","bVImaj7","bVI7","bVII","bVII7","bIII","bIII7","iv","iv7","bII","bII:1"],
      "secondary":   ["V/ii","V/iii","V/IV","V/vi","V7/ii","V7/IV","V7/vi","V7/bII"],
    },
    "minor": {
      "tonic":       ["i","i:1","III","IIImaj7","VI","VImaj7","I"],
      "predominant": ["iio","iih7","iio:1","iv","iv7","iv:1","II","IVmaj7"],
      "dominant":    ["V","V7","V7:1","V7:3","V9","viio","viio7","viih7","VII","VII7"],
      "borrowed":    ["IV","IVmaj7","bII","bII:1"],
      "secondary":   ["V/III","V/VI","V7/III","V7/VI","V/iv","V7/iv"],
    },
  };

  const FUNCTIONAL_ROLE = {
    "I:2":"dominant",
    "bVI":"predominant","bVImaj7":"predominant","bVI7":"predominant",
    "bVII":"predominant","bVII7":"predominant",
    "bIII":"tonic","bIIImaj7":"tonic","bIII7":"tonic",
    "iv":"predominant","iv7":"predominant","iv:1":"predominant",
    "bII":"predominant","bII:1":"predominant",
    "II":"predominant","IV":"predominant","IVmaj7":"predominant",
    "I":"tonic",
    "V/ii":"predominant","V7/ii":"predominant",
    "V/iii":"tonic",
    "V/IV":"predominant","V7/IV":"predominant",
    "V/V":"dominant","V7/V":"dominant",
    "V/vi":"tonic","V7/vi":"tonic",
    "V/III":"tonic","V7/III":"tonic",
    "V/VI":"predominant","V7/VI":"predominant",
    "V/iv":"predominant","V7/iv":"predominant",
    "V7/bII":"predominant",
    "VII":"dominant","VII7":"dominant","viio7":"dominant",
  };

  // ───────────────────────────────────────────────
  // Helpers
  // ───────────────────────────────────────────────

  function keyRootPc(keyStr) {
    const n = keyStr[0];
    const acc = keyStr.slice(1);
    const base = (n in NOTE_TO_PC) ? NOTE_TO_PC[n] : 0;
    const d = {'#':1,'##':2,'b':-1,'bb':-2}[acc] || 0;
    return ((base + d) % 12 + 12) % 12;
  }

  function sharpsOf(keyStr) {
    return (keyStr in KEY_SIGS) ? KEY_SIGS[keyStr] : 0;
  }

  function spell(midi, sharps) {
    const pc = ((midi % 12) + 12) % 12;
    const octave = Math.floor(midi / 12) - 1;
    const names = sharps > 0 ? SHARP_NAMES : FLAT_NAMES;
    return `${names[pc]}${octave}`;
  }

  function noteNameToPc(name) {
    return (name in NOTE_TO_PC) ? NOTE_TO_PC[name] : 0;
  }

  function splitColon(numeral) {
    const idx = numeral.lastIndexOf(':');
    if (idx >= 0) {
      const base = numeral.slice(0, idx);
      const invS = numeral.slice(idx + 1);
      const n = parseInt(invS, 10);
      if (!isNaN(n) && /^-?\d+$/.test(invS)) {
        return [base, n];
      }
    }
    return [numeral, 0];
  }

  function parseNumeral(numeral, keyPc, sharps) {
    const [baseNum, colonInv] = splitColon(numeral);
    const s = baseNum.trim();

    // Secondary: V7/ii — resolve /ii first, use its root as new key
    if (s.indexOf('/') >= 0) {
      const idx = s.indexOf('/');
      const primaryStr = s.slice(0, idx);
      const secondaryStr = s.slice(idx + 1);
      const sec = parseNumeral(secondaryStr, keyPc, sharps);
      if (sec === null) return null;
      const newKeyPc = ((keyPc + sec.root_offset) % 12 + 12) % 12;
      const result = parseNumeral(primaryStr, newKeyPc, sharps);
      if (result) {
        result.name = `${result.name} / ${sec.name}`;
      }
      return result;
    }

    const m = s.match(RN_RE);
    if (!m) return null;
    const accS = m[1];
    const degS = m[2];
    const triadMod = m[3];
    const ext = m[4];
    const invS = m[5];
    // m[6] = secondary, already handled above

    const degUpper = degS.toUpperCase();
    if (!(degUpper in DEGREE_SEMITONES)) return null;

    const degOffset = DEGREE_SEMITONES[degUpper];
    const accOffset = {'b':-1,'bb':-2,'#':1,'##':2}[accS] || 0;
    const rootOffset = ((degOffset + accOffset) % 12 + 12) % 12;
    const rootPc = ((keyPc + rootOffset) % 12 + 12) % 12;

    const isUpper = degS[0] === degS[0].toUpperCase() && degS[0] !== degS[0].toLowerCase();

    // Base triad quality
    let base;
    if (triadMod === '+' || triadMod === 'aug') base = 'aug';
    else if (triadMod === 'o' || triadMod === 'dim') base = 'dim';
    else if (triadMod === 'h') base = 'halfdim';
    else if (isUpper) base = 'maj';
    else base = 'min';

    // Resolve quality from base + extension
    let quality;
    if (triadMod === 'h' || ext === 'm7b5') {
      quality = 'halfdim';
    } else if (ext === 'maj7' || ext === 'maj9') {
      quality = (base === 'maj') ? 'maj7' : (base === 'min' ? 'mmaj7' : 'maj7');
      if (ext === 'maj9') quality = 'maj9';
    } else if (ext === 'mMaj7') {
      quality = 'mmaj7';
    } else if (ext === '7') {
      const q = {'maj':'dom7','min':'m7','dim':'dim7','aug':'aug7','halfdim':'halfdim'};
      quality = (base in q) ? q[base] : 'dom7';
    } else if (ext === '9') {
      quality = (base === 'maj') ? 'dom9' : 'm9';
    } else if (ext === 'sus4') {
      quality = 'sus4';
    } else if (ext === 'sus47') {
      quality = 'sus47';
    } else if (ext === 'sus2') {
      quality = 'sus2';
    } else {
      quality = base;
    }

    if (!(quality in INTERVALS)) quality = base;

    const intervals = INTERVALS[quality];
    const figured = {'6':1,'64':2,'65':1,'43':2,'42':3};
    const defaultInversion = colonInv ? colonInv : (figured[invS] || 0);

    const pitchPcs = intervals.map(i => ((rootPc + i) % 12 + 12) % 12);
    const namesList = sharps > 0 ? SHARP_NAMES : FLAT_NAMES;
    const noteNames = pitchPcs.map(pc => namesList[pc]);

    return {
      root_offset: rootOffset,
      root_pc: rootPc,
      intervals: intervals,
      quality: quality,
      name: QUALITY_NAMES[quality] || quality,
      note_names: noteNames,
      default_inversion: defaultInversion,
    };
  }

  // ───────────────────────────────────────────────
  // Voicing engine
  // ───────────────────────────────────────────────

  function initialVoicing(noteNames, n) {
    n = n || 4;
    const result = [];
    let current = 48; // C3
    for (let i = 0; i < n; i++) {
      const name = noteNames[i % noteNames.length];
      const pc = noteNameToPc(name);
      const octave = Math.floor(current / 12) - 1;
      let midi = (octave + 1) * 12 + pc;
      while (midi < current) midi += 12;
      result.push(midi);
      current = midi + 2;
    }
    return result;
  }

  function voiceLeadStep(prev, noteNames) {
    const midiToName = {};
    const allCandidates = [];
    for (const name of noteNames) {
      const pc = noteNameToPc(name);
      for (let octave = 1; octave < 8; octave++) {
        const m = (octave + 1) * 12 + pc;
        midiToName[m] = name;
        allCandidates.push(m);
      }
    }

    const result = new Array(prev.length).fill(null);
    const usedMidis = new Set();
    const coveredNames = new Set();

    // Order voices by which has the closest possible candidate
    const order = prev.map((_, i) => i).sort((a, b) => {
      const minA = Math.min(...allCandidates.map(m => Math.abs(m - prev[a])));
      const minB = Math.min(...allCandidates.map(m => Math.abs(m - prev[b])));
      return minA - minB;
    });

    for (const i of order) {
      const uncovered = noteNames.filter(nm => !coveredNames.has(nm));
      let pool = allCandidates.filter(m => uncovered.indexOf(midiToName[m]) >= 0 && !usedMidis.has(m));
      if (pool.length === 0) {
        // All chord tones covered — must double. Prefer root, then 5th, never 3rd.
        const root = noteNames[0];
        const fifth = noteNames.length >= 3 ? noteNames[2] : null;
        let doublePool = allCandidates.filter(m => midiToName[m] === root && !usedMidis.has(m));
        if (doublePool.length === 0 && fifth)
          doublePool = allCandidates.filter(m => midiToName[m] === fifth && !usedMidis.has(m));
        if (doublePool.length === 0)
          doublePool = allCandidates.filter(m => !usedMidis.has(m));
        pool = doublePool;
      }
      if (pool.length === 0) pool = allCandidates.slice();
      let best = pool[0];
      let bestD = Math.abs(best - prev[i]);
      for (const m of pool) {
        const d = Math.abs(m - prev[i]);
        if (d < bestD) { bestD = d; best = m; }
      }
      result[i] = best;
      usedMidis.add(best);
      coveredNames.add(midiToName[best]);
    }

    return result;
  }

  function enforceInversion(voices, noteNames, inversion) {
    if (!noteNames || noteNames.length === 0 || inversion === -1) return voices;
    voices = voices.slice().sort((a, b) => a - b);
    const targetName = noteNames[((inversion % noteNames.length) + noteNames.length) % noteNames.length];
    const targetPc = noteNameToPc(targetName);

    if (((voices[0] % 12) + 12) % 12 === targetPc) return voices;

    const oldBassPc = ((voices[0] % 12) + 12) % 12;
    const ceiling = voices.length > 1 ? voices[1] : voices[0];
    let newBass = null;
    let bestDist = 999;
    for (let octave = 1; octave < 7; octave++) {
      const midi = (octave + 1) * 12 + targetPc;
      if (midi < ceiling) {
        const d = Math.abs(midi - voices[0]);
        if (d < bestDist) { bestDist = d; newBass = midi; }
      }
    }
    if (newBass === null) return voices;

    const oldBassPresentUpper = voices.slice(1).some(v => (((v % 12) + 12) % 12) === oldBassPc);
    const oldBassName = noteNames.find(n => noteNameToPc(n) === oldBassPc) || null;
    voices[0] = newBass;

    if (!oldBassPresentUpper && oldBassName) {
      for (let i = 1; i < voices.length; i++) {
        if ((((voices[i] % 12) + 12) % 12) === targetPc) {
          const ref = voices[i];
          let repl = null;
          let bestD = Infinity;
          for (let oct = 1; oct < 7; oct++) {
            const m = (oct + 1) * 12 + oldBassPc;
            const d = Math.abs(m - ref);
            if (d < bestD) { bestD = d; repl = m; }
          }
          voices[i] = repl;
          break;
        }
      }
    }

    return voices.slice().sort((a, b) => a - b);
  }

  function applyVoicingStyle(voices, style) {
    let v = voices.slice().sort((a, b) => a - b);
    if (style === "drop2" && v.length >= 3) {
      v[v.length - 2] -= 12;
      v.sort((a, b) => a - b);
    } else if (style === "open" && v.length >= 3) {
      v[1] += 12;
      if (v.length >= 4) v[2] += 12;
      v.sort((a, b) => a - b);
    }
    v = v.map(x => x > 79 ? x - 12 : x);
    v = v.map(x => x < 36 ? x + 12 : x);
    return v.sort((a, b) => a - b);
  }

  function computeVoices(progression) {
    const keyPc = keyRootPc(progression.key);
    const sharps = sharpsOf(progression.key);
    const result = [];
    let prev = null;
    const nVoices = progression.n_voices || 4;
    const style = progression.voicing_style || 'close';
    for (const event of progression.chords) {
      const parsed = parseNumeral(event.numeral, keyPc, sharps);
      if (parsed === null) continue;
      const names = parsed.note_names;
      let voices = (prev === null)
        ? initialVoicing(names, nVoices)
        : voiceLeadStep(prev, names);
      voices = voices.slice().sort((a, b) => a - b);
      voices = enforceInversion(voices, names, event.inversion || 0);
      prev = voices.slice();
      voices = applyVoicingStyle(voices, style);
      result.push(voices);
    }
    return result;
  }

  // ───────────────────────────────────────────────
  // Public API: matches FastAPI surface
  // ───────────────────────────────────────────────

  function getChords(key, mode) {
    key = key || 'C';
    mode = mode || 'major';
    const keyPc = keyRootPc(key);
    const sharps = sharpsOf(key);
    const funcs = FUNCTION_MAP[mode] || FUNCTION_MAP['major'];
    const result = {};
    for (const fn of Object.keys(funcs)) {
      result[fn] = [];
      for (const n of funcs[fn]) {
        const parsed = parseNumeral(n, keyPc, sharps);
        if (parsed === null) continue;
        result[fn].push({
          numeral: n,
          name: parsed.name,
          pitches: parsed.note_names.map(nm => `${nm}4`),
          duration_default: 4.0,
          fn: fn,
          fn_role: FUNCTIONAL_ROLE[n] || fn,
          default_inversion: parsed.default_inversion,
        });
      }
    }
    return result;
  }

  function parseChord(numeral, key, mode) {
    key = key || 'C';
    const keyPc = keyRootPc(key);
    const sharps = sharpsOf(key);
    const parsed = parseNumeral(numeral, keyPc, sharps);
    if (parsed === null) return { error: `Cannot parse '${numeral}'` };
    return {
      numeral: numeral,
      name: parsed.name,
      pitches: parsed.note_names.map(nm => `${nm}4`),
      duration_default: 4.0,
      fn: null,
      default_inversion: parsed.default_inversion,
    };
  }

  function voiceLead(params) {
    const progression = normalizeProgression(params);
    const sharps = sharpsOf(progression.key);
    const keyPc = keyRootPc(progression.key);
    const allVoices = computeVoices(progression);
    const validChords = progression.chords.filter(
      e => parseNumeral(e.numeral, keyPc, sharps) !== null
    );
    const table = [];
    for (let i = 0; i < validChords.length; i++) {
      const event = validChords[i];
      const voices = allVoices[i];
      const row = { numeral: event.numeral, duration: event.duration, voices: [] };
      for (let j = 0; j < voices.length; j++) {
        const delta = i > 0 ? voices[j] - allVoices[i - 1][j] : null;
        row.voices.push({ pitch: spell(voices[j], sharps), delta: delta });
      }
      table.push(row);
    }
    const voicedChords = validChords.map((e, idx) => ({
      numeral: e.numeral,
      duration: e.duration,
      inversion: e.inversion || 0,
      voices: allVoices[idx],
    }));
    return {
      progression: Object.assign({}, progression, { chords: voicedChords }),
      table: table,
    };
  }

  function normalizeProgression(p) {
    return {
      key: p.key || 'C',
      mode: p.mode || 'major',
      tempo: p.tempo || 120,
      time_sig: p.time_sig || [4, 4],
      n_voices: p.n_voices || 4,
      voicing_style: p.voicing_style || 'close',
      voice_volumes: p.voice_volumes || [100, 85, 85, 75],
      chords: (p.chords || []).map(c => ({
        numeral: c.numeral,
        duration: (c.duration !== undefined) ? c.duration : 4.0,
        inversion: c.inversion || 0,
        voices: c.voices || [],
      })),
    };
  }

  // ───────────────────────────────────────────────
  // MIDI writer (Standard MIDI File, format 1)
  // ───────────────────────────────────────────────

  function writeVarLen(value) {
    // MIDI variable-length quantity
    const buf = [value & 0x7f];
    value >>>= 7;
    while (value > 0) {
      buf.unshift((value & 0x7f) | 0x80);
      value >>>= 7;
    }
    return buf;
  }

  function u16be(v) { return [(v >> 8) & 0xff, v & 0xff]; }
  function u32be(v) { return [(v >>> 24) & 0xff, (v >>> 16) & 0xff, (v >>> 8) & 0xff, v & 0xff]; }

  function buildTempoTrack(bpm) {
    const microsPerBeat = Math.round(60000000 / bpm);
    const events = [];
    // delta 0, FF 51 03 tt tt tt — set tempo
    events.push(...writeVarLen(0), 0xff, 0x51, 0x03,
      (microsPerBeat >> 16) & 0xff,
      (microsPerBeat >> 8) & 0xff,
      microsPerBeat & 0xff);
    // delta 0, FF 2F 00 — end of track
    events.push(...writeVarLen(0), 0xff, 0x2f, 0x00);
    return events;
  }

  function buildVoiceTrack(voiceIdx, validChords, allVoices, ticksPerBeat, velocity) {
    const events = [];
    // Track name meta: FF 03 len <name>
    const name = `Voice ${voiceIdx + 1}`;
    const nameBytes = [];
    for (let i = 0; i < name.length; i++) nameBytes.push(name.charCodeAt(i) & 0xff);
    events.push(...writeVarLen(0), 0xff, 0x03, ...writeVarLen(nameBytes.length), ...nameBytes);

    const channel = voiceIdx & 0x0f;
    const vel = Math.max(1, Math.min(127, velocity));
    for (let i = 0; i < validChords.length; i++) {
      const event = validChords[i];
      const note = allVoices[i][voiceIdx];
      const durTicks = Math.round(ticksPerBeat * event.duration);
      // note on, delta 0
      events.push(...writeVarLen(0), 0x90 | channel, note & 0x7f, vel & 0x7f);
      // note off after durTicks
      events.push(...writeVarLen(durTicks), 0x80 | channel, note & 0x7f, 0x00);
    }
    // End of track
    events.push(...writeVarLen(0), 0xff, 0x2f, 0x00);
    return events;
  }

  function wrapTrack(eventBytes) {
    return [0x4d, 0x54, 0x72, 0x6b, ...u32be(eventBytes.length), ...eventBytes];
  }

  function exportMidi(params) {
    const progression = normalizeProgression(params);
    const keyPc = keyRootPc(progression.key);
    const sharps = sharpsOf(progression.key);
    const allVoices = computeVoices(progression);
    const validChords = progression.chords.filter(
      e => parseNumeral(e.numeral, keyPc, sharps) !== null
    );
    const ticksPerBeat = 480;
    const nVoices = progression.n_voices;
    const volumes = progression.voice_volumes;

    const tracks = [];
    tracks.push(wrapTrack(buildTempoTrack(progression.tempo)));
    for (let v = 0; v < nVoices; v++) {
      const vel = (volumes[v] !== undefined) ? volumes[v] : 85;
      tracks.push(wrapTrack(buildVoiceTrack(v, validChords, allVoices, ticksPerBeat, vel)));
    }

    // Header: MThd, length 6, format 1, ntrks, division
    const header = [
      0x4d, 0x54, 0x68, 0x64,
      ...u32be(6),
      ...u16be(1),
      ...u16be(tracks.length),
      ...u16be(ticksPerBeat),
    ];

    // Flatten
    let total = header.length;
    for (const t of tracks) total += t.length;
    const out = new Uint8Array(total);
    let off = 0;
    out.set(header, off); off += header.length;
    for (const t of tracks) { out.set(t, off); off += t.length; }
    return out;
  }

  // ───────────────────────────────────────────────
  // Export
  // ───────────────────────────────────────────────

  const Engine = { getChords, parseChord, voiceLead, exportMidi, spell };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Engine;
  } else {
    global.Engine = Engine;
  }
})(typeof window !== 'undefined' ? window : globalThis);
