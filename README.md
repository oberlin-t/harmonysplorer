# Harmonysplorer

A chord progression explorer and voice-leading tool for isomorphic MIDI controllers (LinnStrument, Lumatone, Axis-49) and Reaper-based workflows.

Build progressions by function, hear voice-led 4-voice output, export per-voice MIDI tracks to record into your DAW one voice at a time.

**[Try it live →](https://toberlino.github.io/harmonysplorer)**

---

## Features

- **Chord bank** organised by harmonic function (Tonic / Pre-dominant / Dominant) with diatonic, borrowed, and secondary dominant chords
- **4-voice leading** — greedy nearest-pitch algorithm with correct doubling (root > 5th) and inversion enforcement
- **Colon inversion notation** — `I:2`, `V7:1` sets inversion directly in the chord name
- **Voicing styles** — close, drop-2, open
- **Per-voice volume** sliders with MIDI velocity output
- **MIDI export** — one track per voice, drag into Reaper
- **Parallel 5th/octave warnings** in the voice table
- **Waveform preview** — triangle, sine, square, sawtooth
- **LocalStorage persistence** — progression survives page reload
- **JSON project save/load**
- **Zero dependencies** — single `index.html` file, runs locally or on GitHub Pages

---

## Notation

Harmonysplorer uses a jazz-convention Roman numeral system. All notation is keyboard-typeable.

### Chord quality

| Notation | Meaning | Example (C major) |
|---|---|---|
| `I` | Major triad | C E G |
| `i` | Minor triad | C Eb G |
| `I7` | Dominant 7th (major triad + b7) | C E G Bb |
| `Imaj7` | Major 7th (major triad + maj7) | C E G B |
| `i7` | Minor 7th (minor triad + b7) | C Eb G Bb |
| `imaj7` | Minor-major 7th | C Eb G B |
| `viih7` | Half-diminished (`h` = half-dim) | B D F A |
| `viio7` | Fully diminished | B D F Ab |
| `Isus4` | Suspended 4th | C F G |
| `V9` | Dominant 9th (drop-5 voicing) | G B F A |

**Key rule:** `7` always means a minor 7th interval (jazz convention). `maj7` always means a major 7th. This is unambiguous regardless of chord degree.

### Accidentals

Prefix the Roman numeral with `b` (flat) or `#` (sharp):

```
bVI     →  Ab major in C
bVII7   →  Bb dominant 7th in C
bVI7    →  Ab dominant 7th (Ab C Eb Gb) in C
#IV     →  F# major in C
```

Double accidentals: `bb`, `##`.

### Inversions

Append `:N` to set the default inversion (which chord tone is in the bass):

```
I:1     →  I in first inversion  (3rd in bass)
I:2     →  I in second inversion (5th in bass) — cadential 6/4
V7:1    →  V7 first inversion    (3rd in bass) — smooth bass line
V7:3    →  V7 third inversion    (7th in bass) — descending bass
bII:1   →  Neapolitan sixth      (3rd in bass)
```

Inversions can also be changed per-chord in the progression table by clicking the chord numeral and retyping (e.g. change `I` to `I:2`).

### Secondary dominants

Use `/` to denote the chord being applied to:

```
V/V     →  D major in C  (dominant of the dominant)
V7/ii   →  A7 in C       (dominant of ii, pre-dominant function)
V7/bII  →  Ab7 in C      (dominant of the Neapolitan)
```

Combinations work: `V7:1/ii` = first inversion V7 of ii.

---

## Usage

1. **Pick chords** from the bank on the left (hover to preview, click to add)
2. **Type custom chords** in the input box at the bottom — any valid Roman numeral
3. **Click a chord numeral** in the table to edit it inline
4. **Scroll** over duration, inversion dropdowns, or sliders to adjust
5. **Drag** rows to reorder
6. **▶ Play** to hear it, **⟳ Loop** to repeat, **⬇ MIDI** to export

### Workflow with LinnStrument

The voice table shows each chord's pitches per voice with interval deltas. Record each voice monophonically into Reaper — the delta column tells you how many semitones to move on the isomorphic grid (same shape = same interval regardless of key).

---

## Running locally

Just open `index.html` in any browser — no server, no install, no build step.

```bash
# Or serve with Python if you prefer a local URL:
python3 -m http.server 8080
```

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app (self-contained) |
| `engine.js` | Chord engine as a standalone module (for dev/testing) |
| `SPEC.md` | Original design spec |

---

## Chord engine conventions

- Jazz notation throughout
- `7` = minor 7th (dominant quality on major root, minor 7th on minor root)
- `maj7` = major 7th
- `h` modifier = half-diminished (e.g. `viih7`)
- `o` modifier = diminished triad
- Colon suffix = default inversion index (0=root, 1=first, 2=second, 3=third, -1=auto)
- 4-voice doubling: all chord tones covered first; when doubling required, root preferred over 5th, never 3rd
