"""Split a score into the practiced part and an auto-played accompaniment.

A duet score declares its left-hand part (MusicXML ``<part id="P2">``). The
learner plays everything else; the declared part is played by the synth, so
the left hand never enters the follow judgment, the window plan or the
practice total.

Pure data only: no Qt, no audio, no score parsing.
"""

from __future__ import annotations

from dataclasses import replace

from .score import Score, ScoreNote


def split_accompaniment(
    score: Score, part: str
) -> tuple[Score, tuple[ScoreNote, ...]]:
    """Return ``(practice_score, accompaniment_notes)``.

    A blank declaration, an unknown part id, or a part that holds every note
    returns the original score untouched: bad content metadata must never
    silently remove the learner's practice material.
    """
    if not part:
        return score, ()
    accompaniment = tuple(note for note in score.notes if note.part == part)
    if not accompaniment:
        return score, ()
    practice_notes = [note for note in score.notes if note.part != part]
    if not practice_notes:
        return score, ()
    return replace(score, notes=practice_notes), accompaniment
