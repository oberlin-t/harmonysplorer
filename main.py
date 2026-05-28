from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import mido
from mido import MidiFile, MidiTrack, Message
import tempfile
from music21 import roman, key as m21key, pitch

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
    voicing_style: str = "close"  # close | drop2 | open
    voice_volumes: list[int] = [100, 85, 85, 75]  # 0-100 per voice


# --- Theory helpers ---

FUNCTION_MAP = {
    "major": {
        "tonic":       ["I", "Imaj7", "I6", "iii", "iii7", "vi", "vi7"],
        "predominant": ["ii", "ii7", "ii6", "IV", "IVmaj7", "IV6"],
        "dominant":    ["I64", "V", "V7", "V9", "viio", "viiø7", "V/V", "V7/V"],
        "borrowed":    ["bVI", "bVImaj7", "bVII", "bVII7", "bIII", "bIII7", "iv", "iv7", "bII", "bII6"],
        "secondary":   ["V/ii", "V/iii", "V/IV", "V/vi", "V7/ii", "V7/IV", "V7/vi"],
    },
    "minor": {
        "tonic":       ["i", "imaj7", "i6", "III", "IIImaj7", "VI", "VImaj7", "I"],
        "predominant": ["iio", "iiø7", "iio6", "iv", "iv7", "iv6", "II", "IVmaj7"],
        "dominant":    ["V", "V7", "V9", "viio", "viio7", "viiø7", "VII", "VII7"],
        "borrowed":    ["IV", "bVII", "bVII7", "bIII", "bIIImaj7"],
        "secondary":   ["V/III", "V/VI", "V7/III", "V7/VI", "V/iv", "V7/iv"],
    },
}

# Functional role when viewing borrowed/secondary chords by harmonic function
FUNCTIONAL_ROLE = {
    "I64":    "dominant",
    "bVI":    "predominant", "bVImaj7": "predominant",
    "bVII":   "predominant", "bVII7":   "predominant",
    "bIII":   "tonic",       "bIIImaj7":"tonic",
    "iv":     "predominant", "iv7":     "predominant",  "iv6": "predominant",
    "bII":    "predominant", "bII6":    "predominant",
    "II":     "predominant", "IV":      "predominant",
    "IVmaj7": "predominant",
    "I":      "tonic",       # Picardy third in minor
    "V/ii":   "predominant", "V7/ii":   "predominant",
    "V/iii":  "tonic",
    "V/IV":   "predominant", "V7/IV":   "predominant",
    "V/V":    "dominant",    "V7/V":    "dominant",
    "V/vi":   "tonic",       "V7/vi":   "tonic",
    "V/III":  "tonic",       "V7/III":  "tonic",
    "V/VI":   "predominant", "V7/VI":   "predominant",
    "V/iv":   "predominant", "V7/iv":   "predominant",
    "VII":    "dominant",    "VII7":    "dominant",
    "viio7":  "dominant",
}

DURATION_DEFAULTS = {
    "tonic": 4.0,
    "predominant": 4.0,
    "dominant": 4.0,
    "borrowed": 4.0,
    "secondary": 4.0,
}


def get_key(key_str: str, mode: str) -> m21key.Key:
    return m21key.Key(key_str, mode if mode in ("major", "minor") else "major")


def spell_pitch(midi_val: int, k: m21key.Key) -> str:
    p = pitch.Pitch(midi=midi_val)
    # Prefer flat spelling for flat/neutral keys (C major and below use flats for borrowed chords)
    if p.accidental and p.accidental.name == 'sharp' and k.sharps <= 0:
        enh = p.getEnharmonic()
        if enh.accidental is None or enh.accidental.name == 'flat':
            p = enh
    return str(p)


def initial_voicing(names: list[str], n: int = 4) -> list[int]:
    result = []
    current = 48  # C3
    for i in range(n):
        name = names[i % len(names)]
        p = pitch.Pitch(name)
        p.octave = (current // 12) - 1
        while p.midi < current:
            p.octave += 1
        result.append(p.midi)
        current = p.midi + 2
    return result


def voice_lead_step(prev: list[int], names: list[str]) -> list[int]:
    # Build candidate MIDI pitches with name lookup
    midi_to_name = {}
    all_candidates = []
    for name in names:
        for octave in range(2, 8):
            m = pitch.Pitch(f"{name}{octave}").midi
            midi_to_name[m] = name
            all_candidates.append(m)

    result = [None] * len(prev)
    used_midis = set()
    covered_names = set()

    order = sorted(range(len(prev)), key=lambda i: min(abs(m - prev[i]) for m in all_candidates))

    for i in order:
        best, best_dist = None, 999
        uncovered = [n for n in names if n not in covered_names]

        # Pass 1: prefer pitches of uncovered chord tones (ensures 7th always included)
        pool = [m for m in all_candidates if midi_to_name[m] in uncovered and m not in used_midis]
        # Pass 2: any unused pitch
        if not pool:
            pool = [m for m in all_candidates if m not in used_midis]
        # Pass 3: allow doubling if all pitches somehow exhausted
        if not pool:
            pool = all_candidates

        for m in pool:
            d = abs(m - prev[i])
            if d < best_dist:
                best_dist, best = d, m

        result[i] = best
        used_midis.add(best)
        covered_names.add(midi_to_name[best])

    return result


def enforce_inversion(voices: list[int], names: list[str], inversion: int) -> list[int]:
    if not names or inversion == -1:  # -1 = auto: let voice leading decide
        return voices
    target = names[inversion % len(names)]
    # Find closest pitch with target name that sits below voice index 1
    ceiling = voices[1] if len(voices) > 1 else voices[0]
    best, best_dist = None, 999
    for octave in range(1, 7):
        p = pitch.Pitch(f"{target}{octave}")
        if p.midi < ceiling:
            d = abs(p.midi - voices[0])
            if d < best_dist:
                best_dist, best = d, p.midi
    if best:
        voices = list(voices)
        voices[0] = best
    return voices


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
    # Clamp: pull anything above G5 (79) down an octave, anything below C2 (36) up
    v = [x - 12 if x > 79 else x for x in v]
    v = [x + 12 if x < 36 else x for x in v]
    return sorted(v)


def compute_voices(progression: Progression) -> list[list[int]]:
    k = get_key(progression.key, progression.mode)
    result = []
    prev = None
    for event in progression.chords:
        rn = roman.RomanNumeral(event.numeral, k)
        names = [p.name for p in rn.pitches]
        voices = initial_voicing(names, progression.n_voices) if prev is None else voice_lead_step(prev, names)
        voices = sorted(voices)
        voices = enforce_inversion(voices, names, event.inversion)
        # Store close-position voices as prev so style doesn't compound across steps
        prev = list(voices)
        voices = apply_voicing_style(voices, progression.voicing_style)
        result.append(voices)
    return result


# --- Routes ---

@app.get("/")
def index():
    return FileResponse("index.html")


@app.get("/chords")
def get_chords(key: str = "C", mode: str = "major"):
    k = get_key(key, mode)
    funcs = FUNCTION_MAP.get(mode, FUNCTION_MAP["major"])
    result = {}
    for fn, numerals in funcs.items():
        result[fn] = []
        for n in numerals:
            try:
                rn = roman.RomanNumeral(n, k)
                result[fn].append({
                    "numeral": n,
                    "name": rn.commonName,
                    "pitches": [str(p) for p in rn.pitches],
                    "duration_default": DURATION_DEFAULTS[fn],
                    "fn": fn,
                    "fn_role": FUNCTIONAL_ROLE.get(n, fn),
                })
            except Exception:
                pass
    return result


@app.post("/parse-chord")
def parse_chord(data: dict):
    k = get_key(data.get("key", "C"), data.get("mode", "major"))
    try:
        rn = roman.RomanNumeral(data["numeral"], k)
        return {
            "numeral": data["numeral"],
            "name": rn.commonName,
            "pitches": [str(p) for p in rn.pitches],
            "duration_default": 2.0,
            "fn": None,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/voice-lead")
def voice_lead_route(progression: Progression):
    k = get_key(progression.key, progression.mode)
    all_voices = compute_voices(progression)
    table = []
    for i, (event, voices) in enumerate(zip(progression.chords, all_voices)):
        row = {"numeral": event.numeral, "duration": event.duration, "voices": []}
        for j, midi in enumerate(voices):
            delta = midi - all_voices[i-1][j] if i > 0 else None
            row["voices"].append({"pitch": spell_pitch(midi, k), "delta": delta})
        table.append(row)
    voiced_chords = [
        ChordEvent(numeral=e.numeral, duration=e.duration, voices=v)
        for e, v in zip(progression.chords, all_voices)
    ]
    return {
        "progression": Progression(**{**progression.model_dump(), "chords": [c.model_dump() for c in voiced_chords]}),
        "table": table,
    }


@app.post("/preview/chord")
def preview_chord(data: dict):
    k = get_key(data.get("key", "C"), data.get("mode", "major"))
    rn = roman.RomanNumeral(data["numeral"], k)
    names = [p.name for p in rn.pitches]
    voices = initial_voicing(names, 4)

    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    duration = 480 * 2
    for note in voices:
        track.append(Message("note_on", note=note, velocity=80, time=0))
    for note in voices:
        track.append(Message("note_off", note=note, velocity=0, time=duration))

    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    mid.save(tmp.name)
    return FileResponse(tmp.name, media_type="audio/midi", filename="preview.mid")


@app.post("/export/midi")
def export_midi(progression: Progression):
    all_voices = compute_voices(progression)
    tpb = 480
    mid = MidiFile(ticks_per_beat=tpb)
    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(progression.tempo), time=0))

    for v in range(progression.n_voices):
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=f"Voice {v+1}", time=0))
        vel = max(1, min(127, int(progression.voice_volumes[v] / 100 * 100)))
        for event, voices in zip(progression.chords, all_voices):
            dur_ticks = int(tpb * event.duration)
            track.append(Message("note_on", channel=v, note=voices[v], velocity=vel, time=0))
            track.append(Message("note_off", channel=v, note=voices[v], velocity=0, time=dur_ticks))

    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    mid.save(tmp.name)
    return FileResponse(tmp.name, media_type="audio/midi", filename="harmonysplorer.mid")
