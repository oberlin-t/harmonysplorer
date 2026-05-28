# Harmonysplorer

A browser-based chord progression explorer with 4-voice leading.

Build progressions by harmonic function, hear voice-led output in real time, and export per-voice MIDI tracks to record into your DAW.

**[Try it →](https://oberlin-t.github.io/harmonysplorer)**

---

## Features

- Chord bank organised by harmonic function — Tonic, Pre-dominant, Dominant — with diatonic, borrowed, and secondary dominant chords
- 4-voice leading with correct doubling rules (root preferred, never 3rd)
- Colon inversion notation: `I:2`, `V7:1`
- Voicing styles: close, drop-2, open
- Per-voice volume control
- MIDI export — one track per voice
- Parallel 5th / octave warnings
- Real-time audio preview (Web Audio API, no plugins)
- LocalStorage persistence and JSON project save/load
- Zero dependencies — single HTML file, works offline

---

## Usage

1. Pick chords from the bank (hover to preview, click to add)
2. Type custom chords in the input box
3. Click any chord numeral in the table to edit it inline
4. Scroll over duration or sliders to adjust values
5. Drag rows to reorder
6. **▶ Play** to hear, **⟳ Loop** to repeat, **⬇ MIDI** to export

---

## Notation

Standard Roman numerals with jazz convention: `7` always means dominant 7th (minor 7th interval), `maj7` always means major 7th.

| Notation | Meaning | In C major |
|---|---|---|
| `I` | Major triad | C E G |
| `i` | Minor triad | C Eb G |
| `I7` | Dominant 7th | C E G Bb |
| `Imaj7` | Major 7th | C E G B |
| `i7` | Minor 7th | C Eb G Bb |
| `viih7` | Half-diminished (`h`) | B D F A |
| `viio7` | Fully diminished (`o`) | B D F Ab |
| `Isus4` | Suspended 4th | C F G |
| `bVI` | Flat submediant (borrowed) | Ab C Eb |
| `bVI7` | Flat submediant dominant 7th | Ab C Eb Gb |
| `V/V` | Secondary dominant | D F# A |
| `V7/ii` | Secondary dominant 7th | A C# E G |
| `I:1` | First inversion (3rd in bass) | E G C |
| `I:2` | Second inversion / cad. 6/4 | G C E |
| `V7:1` | V7 first inversion | B D F G |
| `V7:3` | V7 third inversion | F G B D |

Accidentals: `b` (flat), `#` (sharp), `bb`, `##`. Combinations work: `V7:1/ii`, `bII:1`.

---

## Running locally

Open `index.html` directly in any browser — no install, no build step, no server.

```bash
# Or with a local server:
python3 -m http.server 8080
```

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app (self-contained) |
| `engine.js` | Chord engine as a standalone JS module |
