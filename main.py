from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import mido
from mido import MidiFile, MidiTrack, Message
import tempfile
import re

app = FastAPI()


# --- Models ---

class ChordEvent(BaseModel):
    numeral: str
    duration: float = 4.0
    inversion: int = 0
    voices: list[int] = []

class Progression(BaseModel):
    key: str = "C"
    mode: str = "major"
    tempo: int = 120
    time_sig: tuple[int, int] = (4, 4)
    chords: list[ChordEvent]
    n_voices: int = 4
    voicing_style: str = "close"
    voice_volumes: list[int] = [100, 85, 85, 75]


# ─────────────────────────────────────────────
# Chord engine (no music21)
# Convention: "7" always = minor 7th (dominant quality on major, minor 7th on minor)
#             "maj7" always = major 7th
#             "o7" / "dim7" = diminished 7th
# ─────────────────────────────────────────────

FLAT_NAMES  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
SHARP_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

KEY_SIGS = {
    'C':0,'G':1,'D':2,'A':3,'E':4,'B':5,'F#':6,'C#':7,
    'F':-1,'Bb':-2,'Eb':-3,'Ab':-4,'Db':-5,'Gb':-6,'Cb':-7,
}

NOTE_TO_PC = {
    'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'E#':5,'Fb':4,
    'F':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,
    'B':11,'B#':0,'Cb':11,
}

DEGREE_SEMITONES = {'I':0,'II':2,'III':4,'IV':5,'V':7,'VI':9,'VII':11}

# Jazz convention: "7" = minor 7th added to the triad
# quality tag → intervals (semitones from root)
INTERVALS: dict[str, list[int]] = {
    'maj':     [0,4,7],
    'min':     [0,3,7],
    'dim':     [0,3,6],
    'aug':     [0,4,8],
    'dom7':    [0,4,7,10],   # major triad + b7
    'maj7':    [0,4,7,11],   # major triad + maj7
    'm7':      [0,3,7,10],   # minor triad + b7
    'mmaj7':   [0,3,7,11],   # minor triad + maj7
    'halfdim': [0,3,6,10],   # dim triad + b7  (h7)
    'dim7':    [0,3,6,9],    # dim triad + bb7 (o7)
    'aug7':    [0,4,8,10],   # aug triad + b7
    'dom9':    [0,4,10,14],  # drop-5 dominant 9
    'maj9':    [0,4,11,14],  # drop-5 major 9
    'm9':      [0,3,10,14],  # drop-5 minor 9
    'sus4':    [0,5,7],
    'sus2':    [0,2,7],
    'sus47':   [0,5,7,10],
}

QUALITY_NAMES = {
    'maj':'major triad','min':'minor triad','dim':'diminished triad','aug':'augmented triad',
    'dom7':'dominant 7th','maj7':'major 7th','m7':'minor 7th',
    'mmaj7':'minor-major 7th','halfdim':'half-diminished 7th','dim7':'diminished 7th',
    'aug7':'augmented 7th','dom9':'dominant 9th','maj9':'major 9th','m9':'minor 9th',
    'sus4':'suspended 4th','sus2':'suspended 2nd','sus47':'sus4 dom7',
}

# Roman numeral regex
# Groups: accidental | degree | triad-mod | extension | figured-bass | secondary
_RN_RE = re.compile(
    r'^(bb|b|##|#)?'
    r'(VII|VI|IV|III|II|I|vii|vi|iv|iii|ii|i|V|v)'
    r'(\+|aug|h|o)?'
    r'(maj7|maj9|mMaj7|m7b5|m7|sus4(?:7)?|sus2|add9|9|7)?'
    r'(64|65|43|42|6)?'
    r'(?:/(.+))?$'
)

def _key_root_pc(key_str: str) -> int:
    n, acc = key_str[0], key_str[1:]
    base = NOTE_TO_PC.get(n, 0)
    d = {'#':1,'##':2,'b':-1,'bb':-2}.get(acc, 0)
    return (base + d) % 12

def _sharps(key_str: str) -> int:
    return KEY_SIGS.get(key_str, 0)

def spell(midi: int, sharps: int) -> str:
    pc = midi % 12
    octave = (midi // 12) - 1
    names = SHARP_NAMES if sharps > 0 else FLAT_NAMES
    return f"{names[pc]}{octave}"

def note_name_to_pc(name: str) -> int:
    return NOTE_TO_PC.get(name, 0)

def name_midi(note_name: str, octave: int) -> int:
    return (octave + 1) * 12 + note_name_to_pc(note_name)


def split_colon(numeral: str) -> tuple[str, int]:
    """Strip :N inversion suffix. Returns (base_numeral, inversion)."""
    if ':' in numeral:
        base, _, inv_s = numeral.rpartition(':')
        try:
            return base, int(inv_s)
        except ValueError:
            pass
    return numeral, 0


def parse_numeral(numeral: str, key_pc: int, sharps: int) -> dict | None:
    base, colon_inv = split_colon(numeral)
    s = base.strip()

    # Secondary: V7/ii → resolve /ii first, use its root as new key
    if '/' in s:
        idx = s.index('/')
        primary_str = s[:idx]
        secondary_str = s[idx+1:]
        sec = parse_numeral(secondary_str, key_pc, sharps)
        if sec is None:
            return None
        new_key_pc = (key_pc + sec['root_offset']) % 12
        result = parse_numeral(primary_str, new_key_pc, sharps)
        if result:
            result['name'] = f"{result['name']} / {sec['name']}"
        return result

    m = _RN_RE.match(s)
    if not m:
        return None
    acc_s, deg_s, triad_mod, ext, inv_s, _ = m.groups()

    deg_upper = deg_s.upper()
    if deg_upper not in DEGREE_SEMITONES:
        return None

    deg_offset = DEGREE_SEMITONES[deg_upper]
    acc_offset = {'b':-1,'bb':-2,'#':1,'##':2}.get(acc_s, 0)
    root_offset = (deg_offset + acc_offset) % 12
    root_pc = (key_pc + root_offset) % 12

    is_upper = deg_s[0].isupper()

    # Base triad quality
    if triad_mod in ('+', 'aug'):
        base = 'aug'
    elif triad_mod in ('o', 'dim'):
        base = 'dim'
    elif triad_mod == 'h':
        base = 'halfdim'
    elif is_upper:
        base = 'maj'
    else:
        base = 'min'

    # Resolve quality from base + extension
    if triad_mod == 'h' or ext == 'm7b5':
        quality = 'halfdim'
    elif ext == 'maj7' or ext == 'maj9':
        quality = 'maj7' if base == 'maj' else ('mmaj7' if base == 'min' else 'maj7')
        if ext == 'maj9':
            quality = 'maj9'
    elif ext == 'mMaj7':
        quality = 'mmaj7'
    elif ext == '7':
        # Jazz convention: always adds minor 7th (b7)
        q = {'maj':'dom7','min':'m7','dim':'dim7','aug':'aug7','halfdim':'halfdim'}
        quality = q.get(base, 'dom7')
    elif ext == '9':
        quality = 'dom9' if base == 'maj' else 'm9'
    elif ext == 'sus4':
        quality = 'sus4'
    elif ext == 'sus47':
        quality = 'sus47'
    elif ext == 'sus2':
        quality = 'sus2'
    else:
        quality = base

    if quality not in INTERVALS:
        quality = base

    intervals = INTERVALS[quality]
    # Colon notation takes priority over figured bass suffix
    default_inversion = colon_inv if colon_inv else {'6':1,'64':2,'65':1,'43':2,'42':3}.get(inv_s, 0)

    # Pitch classes and note names
    pitch_pcs = [(root_pc + i) % 12 for i in intervals]
    names_list = SHARP_NAMES if sharps > 0 else FLAT_NAMES
    note_names = [names_list[pc] for pc in pitch_pcs]

    return {
        'root_offset': root_offset,
        'root_pc': root_pc,
        'intervals': intervals,
        'quality': quality,
        'name': QUALITY_NAMES.get(quality, quality),
        'note_names': note_names,
        'default_inversion': default_inversion,
    }


# ─────────────────────────────────────────────
# Chord bank
# ─────────────────────────────────────────────

FUNCTION_MAP = {
    "major": {
        "tonic":       ["I","Imaj7","I:1","iii","iii7","vi","vi7"],
        "predominant": ["ii","ii7","ii:1","IV","IVmaj7","IV:1"],
        "dominant":    ["I:2","V","V7","V7:1","V7:3","V9","viio","viih7","V/V","V7/V"],
        "borrowed":    ["bVI","bVImaj7","bVI7","bVII","bVII7","bIII","bIII7","iv","iv7","bII","bII:1"],
        "secondary":   ["V/ii","V/iii","V/IV","V/vi","V7/ii","V7/IV","V7/vi","V7/bII"],
    },
    "minor": {
        "tonic":       ["i","imaj7","i:1","III","IIImaj7","VI","VImaj7","I"],
        "predominant": ["iio","iih7","iio:1","iv","iv7","iv:1","II","IVmaj7"],
        "dominant":    ["V","V7","V7:1","V7:3","V9","viio","viio7","viih7","VII","VII7"],
        "borrowed":    ["IV","bVII","bVII7","bIII","bIIImaj7"],
        "secondary":   ["V/III","V/VI","V7/III","V7/VI","V/iv","V7/iv"],
    },
}

FUNCTIONAL_ROLE = {
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
}


# ─────────────────────────────────────────────
# Voicing engine
# ─────────────────────────────────────────────

def initial_voicing(note_names: list[str], n: int = 4) -> list[int]:
    result = []
    current = 48  # C3
    for i in range(n):
        name = note_names[i % len(note_names)]
        pc = note_name_to_pc(name)
        octave = current // 12 - 1
        midi = (octave + 1) * 12 + pc
        while midi < current:
            midi += 12
        result.append(midi)
        current = midi + 2
    return result


def voice_lead_step(prev: list[int], note_names: list[str]) -> list[int]:
    midi_to_name: dict[int, str] = {}
    all_candidates: list[int] = []
    for name in note_names:
        pc = note_name_to_pc(name)
        for octave in range(1, 8):
            m = (octave + 1) * 12 + pc
            midi_to_name[m] = name
            all_candidates.append(m)

    result: list[int | None] = [None] * len(prev)
    used_midis: set[int] = set()
    covered_names: set[str] = set()

    order = sorted(range(len(prev)), key=lambda i: min(abs(m - prev[i]) for m in all_candidates))

    for i in order:
        uncovered = [nm for nm in note_names if nm not in covered_names]
        pool = [m for m in all_candidates if midi_to_name[m] in uncovered and m not in used_midis]
        if not pool:
            pool = [m for m in all_candidates if m not in used_midis]
        if not pool:
            pool = all_candidates
        best = min(pool, key=lambda m: abs(m - prev[i]))
        result[i] = best
        used_midis.add(best)
        covered_names.add(midi_to_name[best])

    return result  # type: ignore


def enforce_inversion(voices: list[int], note_names: list[str], inversion: int) -> list[int]:
    if not note_names or inversion == -1:
        return voices
    voices = sorted(list(voices))
    target_name = note_names[inversion % len(note_names)]
    target_pc = note_name_to_pc(target_name)

    if voices[0] % 12 == target_pc:
        return voices

    old_bass_pc = voices[0] % 12
    ceiling = voices[1] if len(voices) > 1 else voices[0]
    new_bass, best_dist = None, 999
    for octave in range(1, 7):
        midi = (octave + 1) * 12 + target_pc
        if midi < ceiling:
            d = abs(midi - voices[0])
            if d < best_dist:
                best_dist, new_bass = d, midi
    if new_bass is None:
        return voices

    old_bass_present_upper = any(v % 12 == old_bass_pc for v in voices[1:])
    old_bass_name = next((n for n in note_names if note_name_to_pc(n) == old_bass_pc), None)
    voices[0] = new_bass

    # Displaced chord tone not present in upper voices — rehome it by replacing a doubling
    if not old_bass_present_upper and old_bass_name:
        for i in range(1, len(voices)):
            if voices[i] % 12 == target_pc:
                ref = voices[i]
                repl = min(
                    ((oct + 1) * 12 + old_bass_pc for oct in range(1, 7)),
                    key=lambda m: abs(m - ref)
                )
                voices[i] = repl
                break

    return sorted(voices)


def apply_voicing_style(voices: list[int], style: str) -> list[int]:
    v = sorted(voices)
    if style == "drop2" and len(v) >= 3:
        v[-2] -= 12
        v = sorted(v)
    elif style == "open" and len(v) >= 3:
        v[1] += 12
        if len(v) >= 4:
            v[2] += 12
        v = sorted(v)
    v = [x - 12 if x > 79 else x for x in v]
    v = [x + 12 if x < 36 else x for x in v]
    return sorted(v)


def compute_voices(progression: Progression) -> list[list[int]]:
    key_pc = _key_root_pc(progression.key)
    sharps = _sharps(progression.key)
    result = []
    prev = None
    for event in progression.chords:
        parsed = parse_numeral(event.numeral, key_pc, sharps)
        if parsed is None:
            continue
        names = parsed['note_names']
        voices = initial_voicing(names, progression.n_voices) if prev is None else voice_lead_step(prev, names)
        voices = sorted(voices)
        voices = enforce_inversion(voices, names, event.inversion)
        prev = list(voices)
        voices = apply_voicing_style(voices, progression.voicing_style)
        result.append(voices)
    return result


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse("index.html")

@app.get("/engine.js")
def engine_js():
    return FileResponse("engine.js", media_type="application/javascript")


@app.get("/chords")
def get_chords(key: str = "C", mode: str = "major"):
    key_pc = _key_root_pc(key)
    sharps = _sharps(key)
    funcs = FUNCTION_MAP.get(mode, FUNCTION_MAP["major"])
    result = {}
    for fn, numerals in funcs.items():
        result[fn] = []
        for n in numerals:
            parsed = parse_numeral(n, key_pc, sharps)
            if parsed is None:
                continue
            result[fn].append({
                "numeral": n,
                "name": parsed["name"],
                "pitches": [f"{nm}4" for nm in parsed["note_names"]],
                "duration_default": 4.0,
                "fn": fn,
                "fn_role": FUNCTIONAL_ROLE.get(n, fn),
                "default_inversion": parsed["default_inversion"],
            })
    return result


@app.post("/parse-chord")
def parse_chord_route(data: dict):
    key_pc = _key_root_pc(data.get("key", "C"))
    sharps = _sharps(data.get("key", "C"))
    parsed = parse_numeral(data["numeral"], key_pc, sharps)
    if parsed is None:
        return {"error": f"Cannot parse '{data['numeral']}'"}
    return {
        "numeral": data["numeral"],
        "name": parsed["name"],
        "pitches": [f"{nm}4" for nm in parsed["note_names"]],
        "duration_default": 4.0,
        "fn": None,
        "default_inversion": parsed["default_inversion"],
    }


@app.post("/voice-lead")
def voice_lead_route(progression: Progression):
    sharps = _sharps(progression.key)
    all_voices = compute_voices(progression)
    table = []
    valid_chords = [e for e in progression.chords
                    if parse_numeral(e.numeral, _key_root_pc(progression.key), sharps) is not None]
    for i, (event, voices) in enumerate(zip(valid_chords, all_voices)):
        row = {"numeral": event.numeral, "duration": event.duration, "voices": []}
        for j, midi in enumerate(voices):
            delta = midi - all_voices[i-1][j] if i > 0 else None
            row["voices"].append({"pitch": spell(midi, sharps), "delta": delta})
        table.append(row)
    voiced_chords = [
        ChordEvent(numeral=e.numeral, duration=e.duration, voices=v)
        for e, v in zip(valid_chords, all_voices)
    ]
    return {
        "progression": Progression(**{**progression.model_dump(), "chords": [c.model_dump() for c in voiced_chords]}),
        "table": table,
    }


@app.post("/export/midi")
def export_midi(progression: Progression):
    all_voices = compute_voices(progression)
    key_pc = _key_root_pc(progression.key)
    sharps = _sharps(progression.key)
    valid_chords = [e for e in progression.chords
                    if parse_numeral(e.numeral, key_pc, sharps) is not None]
    tpb = 480
    mid = MidiFile(ticks_per_beat=tpb)
    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(progression.tempo), time=0))
    for v in range(progression.n_voices):
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=f"Voice {v+1}", time=0))
        vel = max(1, min(127, progression.voice_volumes[v]))
        for event, voices in zip(valid_chords, all_voices):
            dur_ticks = int(tpb * event.duration)
            track.append(Message("note_on", channel=v, note=voices[v], velocity=vel, time=0))
            track.append(Message("note_off", channel=v, note=voices[v], velocity=0, time=dur_ticks))
    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    mid.save(tmp.name)
    return FileResponse(tmp.name, media_type="audio/midi", filename="harmonysplorer.mid")
