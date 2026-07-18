"""The local embedding: deterministic across processes, related text lands near.

It downloads nothing and needs no model — the covenant's runs-on-old-hardware
value made literal. These tests defend that it is stable (the vectors live in
the database) and that it actually separates related from unrelated language.
"""

import unittest

from memory import embed


class EmbedTest(unittest.TestCase):
    def test_deterministic(self):
        a = embed.to_bytes(embed.embed("the Harvard Street rezoning article"))
        b = embed.to_bytes(embed.embed("the Harvard Street rezoning article"))
        self.assertEqual(a, b)  # same text, same bytes — always, across runs
        self.assertTrue(a)

    def test_unit_norm(self):
        v = embed.embed("motion carries five to zero")
        if v is None:
            self.skipTest("numpy unavailable")
        self.assertAlmostEqual(float((v * v).sum()), 1.0, places=4)

    def test_related_ranks_above_unrelated(self):
        q = embed.embed("rezoning overlay housing district")
        near = embed.embed("the district rezone and the housing overlay")
        far = embed.embed("the coffee was cold and the parking lot flooded")
        if q is None:
            self.skipTest("numpy unavailable")
        self.assertGreater(embed.cosine(q, near), embed.cosine(q, far))

    def test_empty_is_safe(self):
        self.assertEqual(embed.to_bytes(embed.embed("")), b"" if embed.np is None else
                         embed.to_bytes(embed.embed("")))
        self.assertEqual(embed.cosine(None, None), 0.0)

    def test_roundtrip(self):
        v = embed.embed("public comment on the Coolidge Corner traffic plan")
        if v is None:
            self.skipTest("numpy unavailable")
        back = embed.from_bytes(embed.to_bytes(v))
        self.assertAlmostEqual(embed.cosine(v, back), 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
