# Harmonysplorer

Browser-based chord progression explorer with 4-voice leading. Build progressions by harmonic function, hear voice-led output, export per-voice MIDI.

**[Try it →](https://oberlin-t.github.io/harmonysplorer)**

## Notation

Jazz convention throughout: `7` = dominant 7th, `maj7` = major 7th, `h` = half-diminished, `o` = diminished.

**Inversions** — colon suffix sets which chord tone goes in the bass:
`I:1` (3rd), `I:2` (5th / cadential 6/4), `V7:1` (3rd), `V7:3` (7th)

**Accidentals** — `b`/`#` prefix: `bVI`, `bVI7`, `#IV`

**Secondary dominants** — slash notation: `V7/ii`, `V/V`, `V7/bII`

**Custom input** — type any valid numeral in the box, e.g. `bVI7`, `V7:1/ii`, `viih7`

## Usage

Hover chords to preview, click to add. Click any chord numeral in the table to edit inline. Scroll over duration fields and sliders to adjust. Drag rows to reorder.

**⬇ MIDI** exports one track per voice — record each voice separately into your DAW.

## Run locally

Open `index.html` in any browser. No install, no build step, no server required.
