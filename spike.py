"""
Harmonysplorer spike.
Input: Roman numeral progression + key
Output: voice-leading table (stdout) + MIDI file (one track per voice)

Usage: uv run spike.py [progression] [key] [output.mid]
  e.g. uv run spike.py "I vi IV V" C spike.mid
"""

import sys
import mido
from mido import MidiFile, MidiTrack, Message
from music21 import roman, key as m21key, chord, pitch

TICKS_PER_BEAT = 480
BEATS_PER_CHORD = 4
DEFAULT_TEMPO = 500000  # 120 bpm


def parse_progression(numerals: list[str], k: m21key.Key) -> list[chord.Chord]:
    chords = []
    for n in numerals:
        rn = roman.RomanNumeral(n, k)
        chords.append(rn)
    return chords


def initial_voicing(c: chord.Chord, n_voices: int = 4) -> list[pitch.Pitch]:
    """Spread voices across a comfortable range in close position."""
    pitches = c.pitches  # ascending, within one octave
    # Stack voices starting around middle C area
    base_midi = 48  # C3
    result = []
    p_names = [p.name for p in pitches]
    # Assign voices bottom-up, spacing roughly a third apart
    current = base_midi
    for i in range(n_voices):
        name = p_names[i % len(p_names)]
        p = pitch.Pitch(name)
        p.octave = (current // 12) - 1
        while p.midi < current:
            p.octave += 1
        result.append(pitch.Pitch(midi=p.midi))
        current = p.midi + 2  # minimum spacing
    return result


def voice_lead(prev: list[pitch.Pitch], curr_chord: chord.Chord) -> list[pitch.Pitch]:
    """Greedy: assign each prev voice to nearest pitch in curr_chord."""
    chord_pitch_names = [p.name for p in curr_chord.pitches]
    result = []
    for pv in prev:
        best = None
        best_dist = 999
        for name in chord_pitch_names:
            # Find nearest octave
            for octave in range(2, 8):
                candidate = pitch.Pitch(f"{name}{octave}")
                dist = abs(candidate.midi - pv.midi)
                if dist < best_dist:
                    best_dist = dist
                    best = candidate
        result.append(best)
    return result


def build_voices(chords: list[chord.Chord], n_voices: int = 4) -> list[list[pitch.Pitch]]:
    """Returns list of per-chord voice assignments."""
    voices_per_chord = []
    prev = None
    for c in chords:
        if prev is None:
            assigned = initial_voicing(c, n_voices)
        else:
            assigned = voice_lead(prev, c)
        voices_per_chord.append(assigned)
        prev = assigned
    return voices_per_chord


def print_table(numerals: list[str], voices_per_chord: list[list[pitch.Pitch]]):
    n_voices = len(voices_per_chord[0])
    headers = ["Chord"] + [f"V{i+1}" for i in range(n_voices)]
    col_w = 12

    print("  ".join(h.ljust(col_w) for h in headers))
    print("  ".join("-" * col_w for _ in headers))

    for i, (numeral, voices) in enumerate(zip(numerals, voices_per_chord)):
        row = [numeral.ljust(col_w)]
        for j, p in enumerate(voices):
            if i == 0:
                cell = str(p)
            else:
                prev_p = voices_per_chord[i - 1][j]
                delta = p.midi - prev_p.midi
                sign = "+" if delta >= 0 else ""
                cell = f"{p} ({sign}{delta})"
            row.append(cell.ljust(col_w))
        print("  ".join(row))


def write_midi(voices_per_chord: list[list[pitch.Pitch]], path: str):
    n_voices = len(voices_per_chord[0])
    mid = MidiFile(ticks_per_beat=TICKS_PER_BEAT)

    # Tempo track
    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=DEFAULT_TEMPO, time=0))

    duration = TICKS_PER_BEAT * BEATS_PER_CHORD

    for v in range(n_voices):
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=f"Voice {v+1}", time=0))
        time_cursor = 0
        for chord_voices in voices_per_chord:
            p = chord_voices[v]
            track.append(Message("note_on", channel=v, note=p.midi, velocity=80, time=0))
            track.append(Message("note_off", channel=v, note=p.midi, velocity=0, time=duration))

    mid.save(path)
    print(f"\nMIDI saved: {path}  ({n_voices} tracks, {len(voices_per_chord)} chords)")


def main():
    progression_str = sys.argv[1] if len(sys.argv) > 1 else "I vi IV V"
    key_str = sys.argv[2] if len(sys.argv) > 2 else "C"
    out_path = sys.argv[3] if len(sys.argv) > 3 else "out.mid"

    numerals = progression_str.split()
    k = m21key.Key(key_str)

    print(f"\nKey: {key_str}  |  Progression: {' '.join(numerals)}\n")

    chords = parse_progression(numerals, k)
    voices_per_chord = build_voices(chords)
    print_table(numerals, voices_per_chord)
    write_midi(voices_per_chord, out_path)


if __name__ == "__main__":
    main()
