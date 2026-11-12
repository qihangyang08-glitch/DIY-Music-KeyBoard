"""MusicXML tie merging and repeat expansion (H7b).

Fixtures are tiny inline scores with divisions=1 and no tempo mark, so one
quarter note is 0.5 s at the parser's 120 BPM default. The tests assert the
public Score/ScoreNote contract, never parser internals.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.score import parse_score
from app.core.staff import build_staff_layout


def parse_xml(xml: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.musicxml"
        path.write_text(xml, encoding="utf-8")
        return parse_score(path)


def _kinds(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def note(
    step="C",
    octave=4,
    duration=1,
    tie=None,
    tied=None,
    chord=False,
    rest=False,
    voice=None,
    alter=0,
) -> str:
    bits = []
    if chord:
        bits.append("<chord/>")
    if rest:
        bits.append("<rest/>")
    else:
        alter_xml = f"<alter>{alter}</alter>" if alter else ""
        bits.append(
            f"<pitch><step>{step}</step>{alter_xml}"
            f"<octave>{octave}</octave></pitch>"
        )
    bits.append(f"<duration>{duration}</duration>")
    if voice is not None:
        bits.append(f"<voice>{voice}</voice>")
    for kind in _kinds(tie):
        bits.append(f'<tie type="{kind}"/>')
    if tied is not None:
        bits.append(
            "<notations>"
            + "".join(f'<tied type="{kind}"/>' for kind in _kinds(tied))
            + "</notations>"
        )
    return "<note>" + "".join(bits) + "</note>"


def measure(
    number,
    *content,
    forward=False,
    forward_location=None,
    backward=None,
    ending_start=None,
    ending_stop=None,
) -> str:
    bits = []
    if ending_start:
        bits.append(
            f'<barline location="left"><ending number="{ending_start}" '
            'type="start"/></barline>'
        )
    bits.extend(content)
    if ending_stop or forward or backward is not None:
        items = []
        if ending_stop:
            items.append(
                f'<ending number="{ending_stop}" type="stop"/>'
            )
        if forward:
            items.append('<repeat direction="forward"/>')
        if backward is not None:
            times = "" if backward is True else f' times="{backward}"'
            items.append(f'<repeat direction="backward"{times}/>')
        location = (
            f' location="{forward_location}"'
            if forward_location
            else ""
        )
        bits.append(
            f"<barline{location}>" + "".join(items) + "</barline>"
        )
    return f'<measure number="{number}">' + "".join(bits) + "</measure>"


def score(*measures, parts=None) -> str:
    if parts is None:
        parts = [("P1", measures)]
    part_list = "".join(
        f'<score-part id="{part_id}"><part-name>{part_id}</part-name>'
        "</score-part>"
        for part_id, _ in parts
    )
    parts_xml = "".join(
        f'<part id="{part_id}">' + "".join(items) + "</part>"
        for part_id, items in parts
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="3.1"><part-list>'
        + part_list
        + "</part-list>"
        + parts_xml
        + "</score-partwise>"
    )


class TieTest(unittest.TestCase):
    def test_tie_inside_measure_merges_once(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1, tie="start", tied="start"),
                    note("C", 4, 1, tie="stop", tied="stop"),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 1)
        merged = parsed.notes[0]
        self.assertEqual(
            (merged.midi, merged.start, merged.duration, merged.measure),
            (60, 0.0, 1.0, 1),
        )

    def test_tie_across_barline_keeps_the_first_position(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 4, 4, tie="start")),
                measure(
                    2,
                    note("C", 4, 1, tie="stop"),
                    note("D", 4, 1),
                    note(rest=True, duration=2),
                ),
            )
        )

        notes = sorted(
            (item.midi, round(item.start, 3), round(item.duration, 3), item.measure)
            for item in parsed.notes
        )
        self.assertEqual(notes, [(60, 0.0, 2.5, 1), (62, 2.5, 0.5, 2)])

    def test_tie_chain_merges_three_notes(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1, tie="start"),
                    note(
                        "C",
                        4,
                        1,
                        tie=("stop", "start"),
                        tied=("stop", "start"),
                    ),
                    note("C", 4, 1, tie="stop", tied="stop"),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 1)
        self.assertAlmostEqual(parsed.notes[0].duration, 1.5, places=3)

    def test_rest_breaks_tie_continuity(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1, tie="start"),
                    note(rest=True, duration=1),
                    note("C", 4, 1, tie="stop"),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 2)
        self.assertEqual([round(item.duration, 3) for item in parsed.notes], [0.5, 0.5])

    def test_adjacent_same_pitch_without_tie_is_not_merged(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1),
                    note("C", 4, 1),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 2)
        self.assertEqual([round(item.duration, 3) for item in parsed.notes], [0.5, 0.5])

    def test_notations_only_tie_merges(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1, tied="start"),
                    note("C", 4, 1, tied="stop"),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 1)
        self.assertAlmostEqual(parsed.notes[0].duration, 1.0, places=3)

    def test_tie_does_not_cross_parts(self) -> None:
        parsed = parse_xml(
            score(
                parts=[
                    ("P1", (measure(1, note("C", 4, 4, tie="start")),)),
                    ("P2", (measure(1, note("C", 4, 4, tie="stop")),)),
                ]
            )
        )

        self.assertEqual(len(parsed.notes), 2)
        self.assertEqual(sorted(item.part for item in parsed.notes), ["P1", "P2"])

    def test_chord_members_tie_independently(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 4, 1, tie="start"),
                    note("E", 4, 1, chord=True),
                    note("C", 4, 1, tie="stop"),
                    note("E", 4, 1, chord=True),
                )
            )
        )

        self.assertEqual(len(parsed.notes), 3)
        c_notes = [item for item in parsed.notes if item.midi == 60]
        e_notes = [item for item in parsed.notes if item.midi == 64]
        self.assertEqual(len(c_notes), 1)
        self.assertAlmostEqual(c_notes[0].duration, 1.0, places=3)
        self.assertEqual(len(e_notes), 2)

    def test_tied_note_appears_once_on_the_staff(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 4, 4, tie="start")),
                measure(2, note("C", 4, 4, tie="stop")),
            )
        )

        layout = build_staff_layout(parsed)
        self.assertEqual(len(layout.notes), 1)
        self.assertEqual(layout.notes[0].note.measure, 1)
        self.assertEqual(layout.systems[0].measures[1].notes, ())


class RepeatTest(unittest.TestCase):
    def test_simple_repeat_unrolls_twice(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), backward=True),
                measure(3, note("E", 5, 4)),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 74, 76])
        self.assertEqual(
            [round(item.start, 3) for item in parsed.notes],
            [0.0, 2.0, 4.0, 6.0, 8.0],
        )
        self.assertEqual([item.measure for item in parsed.notes], [1, 2, 3, 4, 5])
        self.assertEqual(parsed.measure_count, 5)
        self.assertAlmostEqual(parsed.duration, 10.0, places=3)

    def test_backward_without_forward_repeats_from_the_part_start(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4)),
                measure(2, note("D", 5, 4), backward=True),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 74])

    def test_repeat_times_three(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), backward=3),
            )
        )

        self.assertEqual(len(parsed.notes), 6)
        self.assertEqual(
            [round(item.start, 3) for item in parsed.notes],
            [0.0, 2.0, 4.0, 6.0, 8.0, 10.0],
        )

    def test_one_measure_repeat_with_left_forward_and_right_backward(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4)),
                measure(
                    2,
                    '<barline location="left"><repeat direction="forward"/>'
                    "</barline>"
                    + note("D", 5, 4)
                    + '<barline location="right"><repeat direction="backward" '
                    'times="2"/></barline>',
                ),
                measure(3, note("E", 5, 4)),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 74, 76])
        self.assertEqual(parsed.measure_count, 4)

    def test_left_barline_backward_ends_before_its_measure(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4)),
                measure(
                    2,
                    '<barline location="left"><repeat direction="forward"/>'
                    "</barline>" + note("D", 5, 4),
                ),
                measure(3, note("E", 5, 4)),
                measure(
                    4,
                    '<barline location="left"><repeat direction="backward" '
                    'times="2"/></barline>' + note("F", 5, 4),
                ),
            )
        )

        self.assertEqual(
            [item.midi for item in parsed.notes], [72, 74, 76, 74, 76, 77]
        )
        self.assertEqual(parsed.measure_count, 6)

    def test_first_ending_only_is_skipped_on_later_passes(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(
                    2,
                    note("D", 5, 4),
                    backward=2,
                    ending_start=1,
                    ending_stop=1,
                ),
                measure(3, note("E", 5, 4)),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 76])
        self.assertEqual(parsed.measure_count, 4)

    def test_right_barline_forward_starts_at_the_next_measure(self) -> None:
        parsed = parse_xml(
            score(
                measure(
                    1,
                    note("C", 5, 4),
                    forward=True,
                    forward_location="right",
                ),
                measure(2, note("D", 5, 4), backward=2),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 74])
        self.assertEqual(parsed.measure_count, 3)

    def test_joint_backward_forward_barline_starts_the_next_section(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), forward=True, backward=2),
                measure(3, note("E", 5, 4), backward=2),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 74, 76, 76])
        self.assertEqual(parsed.measure_count, 6)

    def test_ending_jump_does_not_fire_from_a_skipped_measure(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(
                    2,
                    note("D", 5, 4),
                    backward=3,
                    ending_start=1,
                    ending_stop=1,
                ),
                measure(
                    3,
                    note("E", 5, 4),
                    ending_start="2,3",
                    ending_stop="2,3",
                ),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 76, 72, 76])
        self.assertEqual(parsed.measure_count, 6)

    def test_nested_alternatives_stay_on_the_inner_repeat(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), forward=True),
                measure(
                    3,
                    note("E", 5, 4),
                    backward=2,
                    ending_start=1,
                    ending_stop=1,
                ),
                measure(
                    4,
                    note("F", 5, 4),
                    ending_start=2,
                    ending_stop=2,
                ),
                measure(5, note("G", 5, 4), backward=2),
            )
        )

        self.assertEqual(
            [item.midi for item in parsed.notes],
            [72, 74, 76, 74, 77, 79, 72, 74, 76, 74, 77, 79],
        )
        self.assertEqual(parsed.measure_count, 12)

    def test_first_and_second_endings(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(
                    2,
                    note("D", 5, 4),
                    backward=2,
                    ending_start=1,
                    ending_stop=1,
                ),
                measure(
                    3,
                    note("E", 5, 4),
                    ending_start=2,
                    ending_stop=2,
                ),
            )
        )

        self.assertEqual([item.midi for item in parsed.notes], [72, 74, 72, 76])
        self.assertEqual([item.measure for item in parsed.notes], [1, 2, 3, 4])
        self.assertAlmostEqual(parsed.duration, 8.0, places=3)

    def test_tie_inside_a_repeat_merges_once_per_pass(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4, tie="start"), forward=True),
                measure(2, note("C", 5, 4, tie="stop"), backward=2),
            )
        )

        self.assertEqual(len(parsed.notes), 2)
        self.assertEqual(
            [(round(item.start, 3), round(item.duration, 3)) for item in parsed.notes],
            [(0.0, 4.0), (4.0, 4.0)],
        )
        self.assertEqual([item.measure for item in parsed.notes], [1, 3])
        self.assertEqual(parsed.measure_count, 4)

    def test_tie_across_a_repeat_boundary_merges_only_in_the_final_pass(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("D", 5, 4), forward=True),
                measure(2, note("C", 5, 4, tie="start"), backward=2),
                measure(3, note("C", 5, 4, tie="stop")),
            )
        )

        self.assertEqual(len(parsed.notes), 4)
        self.assertEqual(
            [(item.midi, round(item.start, 3), round(item.duration, 3))
             for item in parsed.notes],
            [(74, 0.0, 2.0), (72, 2.0, 2.0), (74, 4.0, 2.0), (72, 6.0, 4.0)],
        )
        self.assertEqual(parsed.measure_count, 5)

    def test_tie_start_does_not_fuse_across_a_repeat_jump(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 1, tie="start")),
                measure(2, note("C", 5, 1, tie="stop"), forward=True),
                measure(3, note("C", 5, 1, tie="start"), backward=2),
                measure(4, note("C", 5, 1, tie="stop")),
            )
        )

        self.assertEqual(
            [(round(item.start, 3), round(item.duration, 3)) for item in parsed.notes],
            [(0.0, 1.0), (1.0, 0.5), (1.5, 0.5), (2.0, 1.0)],
        )

    def test_expanded_measures_are_renumbered(self) -> None:
        repeated = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), backward=2),
            )
        )
        self.assertEqual([item.measure for item in repeated.notes], [1, 2, 3, 4])

    def test_plain_printed_measure_numbers_are_kept(self) -> None:
        plain = parse_xml(
            score(
                measure(1, note("C", 5, 4)),
                measure(5, note("D", 5, 4)),
            )
        )
        self.assertEqual([item.measure for item in plain.notes], [1, 5])

    def test_multipart_parts_expand_independently(self) -> None:
        parsed = parse_xml(
            score(
                parts=[
                    (
                        "P1",
                        (
                            measure(1, note("C", 5, 4), forward=True),
                            measure(2, note("D", 5, 4), backward=2),
                        ),
                    ),
                    (
                        "P2",
                        (
                            measure(1, note("C", 3, 4)),
                            measure(2, note("D", 3, 4)),
                        ),
                    ),
                ]
            )
        )

        self.assertEqual(len(parsed.notes), 6)
        self.assertEqual(parsed.measure_count, 4)
        self.assertEqual(
            sum(1 for item in parsed.notes if item.part == "P1"), 4
        )
        self.assertEqual(
            sum(1 for item in parsed.notes if item.part == "P2"), 2
        )

    def test_runaway_repeat_is_clamped(self) -> None:
        parsed = parse_xml(
            score(
                measure(1, note("C", 5, 4), forward=True),
                measure(2, note("D", 5, 4), backward=1000000),
            )
        )

        self.assertEqual(len(parsed.notes), 64)  # 32 passes x 2 measures


if __name__ == "__main__":
    unittest.main()
