# Harmonysplorer — Web App Spec

## Data Model

### Key
```python
key: str        # tonic, e.g. "C", "F#"
mode: str       # "major" | "minor" | "dorian" | "mixolydian" | ...
```

### ChordEvent
```python
numeral: str    # Roman numeral, e.g. "V7", "IIm7", "bVII"
duration: float # beats, e.g. 4.0, 2.0, 0.5
voices: list[int]  # MIDI note numbers, one per voice (populated by voice-leading engine)
```

### Progression
```python
key: Key
time_sig: tuple[int, int]  # e.g. (4, 4)
tempo: int                 # BPM
chords: list[ChordEvent]
n_voices: int              # default 4
```

## Harmonic Function Categories

Used to populate the chord picker UI. Diatonic chords only for now.

| Function       | Major          | Minor (natural) |
|----------------|----------------|-----------------|
| Tonic          | I iii vi       | i III VI        |
| Pre-dominant   | IIm IV         | IIø iv          |
| Dominant       | V V7 VII°      | V V7 VII°       |

Secondary dominants and borrowed chords deferred to v2.

## API (FastAPI)

```
GET  /chords?key=C&mode=major
     → { tonic: [...], predominant: [...], dominant: [...] }
     Each chord includes: numeral, name, pitches (for display)

POST /voice-lead
     body: Progression (without voices)
     → Progression (with voices populated)
     Also returns interval delta table for display

POST /export/midi
     body: Progression (with voices)
     → MIDI file download (one track per voice)

POST /preview/chord
     body: { numeral, key, mode }
     → short MIDI file (single chord, 2 beats)
     Frontend plays via Web Audio API
```

No persistence — progression lives in browser state. Save/load deferred.

## Frontend

Single page, three columns:

```
┌─────────────────────────────────────────────────────────────┐
│  Key: [C ▾]  Mode: [major ▾]   Tempo: [120]   [4/4 ▾]      │
├───────────────┬──────────────────────────┬──────────────────┤
│  CHORD PICKER │  PROGRESSION             │  VOICE TABLE     │
│               │                          │                  │
│  Tonic        │  I  [4♩] → vi [2♩] → ... │  Chord V1 V2 V3  │
│  [ I  ]       │                          │  I     ...       │
│  [ iii]       │  [+ add chord]           │  vi    ...       │
│  [ vi ]       │                          │  IV    ...       │
│               │  [▶ play] [⬇ export]     │                  │
│  Pre-dominant │                          │                  │
│  [ IIm]       │                          │                  │
│  [ IV ]       │                          │                  │
│               │                          │                  │
│  Dominant     │                          │                  │
│  [ V  ]       │                          │                  │
│  [ V7 ]       │                          │                  │
│  [ VII°]      │                          │                  │
└───────────────┴──────────────────────────┴──────────────────┘
```

- Clicking a chord in the picker **appends it** to the progression
- Hovering a chord in the picker **previews** it (plays via Web Audio)
- Each chord in the progression has an editable duration (beats)
- Voice table updates live as progression changes
- Export button → downloads MIDI (4 tracks)

## Audio Preview

Browser-side: fetch `/preview/chord` → tiny MIDI → decode + play via Web Audio API.
Library: `midi-player-js` or `MIDI.js` for soundfont playback in browser.
No FluidSynth, no Pipewire.

## Stack

- **Backend:** FastAPI + music21 (Python, uv managed)
- **Frontend:** Single HTML file + vanilla JS (no build step)
- **Audio:** Browser Web Audio API + soundfont library
- **MIDI export:** `mido` (already in deps)

## Harmonic Rhythm Defaults

Suggested duration by function (user can override):
- Tonic: 4 beats
- Pre-dominant: 2 beats
- Dominant: 2 beats (often resolves quickly)

## Out of Scope

- Persistence / save-load
- Microtonal
- Secondary dominants / borrowed chords
- Voice locking
- More than 4 voices
- Mobile layout
