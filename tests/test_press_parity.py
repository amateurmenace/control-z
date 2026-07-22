"""The press transcribes the bake, and this test holds them equal.

`record.press.press` is `web.bake.bake` with two desk assumptions swapped
(the corpus is handed in open; the sidecar resolver points at nothing). Its
own docstring names the cost: "a stage added to `web/bake.py` must be added
here too or the hosted edition quietly ships one plane fewer than the desk's."
Nothing enforced that until this test — bake_kits (specs/20 §7.9 P2) is the
first stage added since, and the drift it would cause (kits on the desk
edition, none on the hosted record) is exactly the class of bug this guards.

So: the ordered sequence of `b.bake_*(…)` stage calls must be identical in
both functions, and both must hand `emit_stubs` the same new plane.
"""

import inspect
import re
import unittest


def _stage_calls(fn) -> list:
    """The ordered `b.bake_*(` stage calls in a function's source."""
    src = inspect.getsource(fn)
    return re.findall(r"\bb\.(bake_\w+)\s*\(", src)


class TestPressMirrorsBake(unittest.TestCase):
    def test_the_stage_sequence_is_identical(self):
        from record.press import press
        from web.bake import bake
        self.assertEqual(
            _stage_calls(bake), _stage_calls(press),
            "record.press.press and web.bake.bake ran different bake_* stages "
            "— add the missing stage to both (record/press.py docstring)")

    def test_bake_kits_is_in_the_sequence(self):
        from web.bake import bake
        self.assertIn("bake_kits", _stage_calls(bake))

    def test_bake_votes_is_in_the_sequence(self):
        """specs/21 P2's plane — the sequence-equality test above then forces
        the hosted press to carry it too."""
        from web.bake import bake
        self.assertIn("bake_votes", _stage_calls(bake))

    def test_both_hand_emit_stubs_the_kits_plane(self):
        from record.press import press
        from web.bake import bake
        for fn in (bake, press):
            src = inspect.getsource(fn)
            self.assertTrue(
                re.search(r"emit\.emit_stubs\(.*?kits=kits.*?\)", src, re.S),
                f"{fn.__module__}.{fn.__name__} does not pass kits= to "
                "emit_stubs — the kit pages would not render")


if __name__ == "__main__":
    unittest.main()
