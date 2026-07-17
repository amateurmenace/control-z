import unittest

from highlighter.insight import (ask, brief, decisions, entities,
                                 participation, questions, topics, word_freq)


def seg(start, end, text, speaker=None):
    return {"start": start, "end": end, "text": text, "speaker": speaker}


MEETING = [
    seg(0, 6, "Call to order, this is the July session of the select board.", "Chair"),
    seg(8, 16, "We have a petition from residents about the crosswalk on Harvard Street safety.", "Clerk"),
    seg(18, 27, "Why does the crosswalk cost so much? What is the timeline for the crosswalk work?", "Resident"),
    seg(30, 40, "I move that we approve the $2 million budget for the crosswalk improvements near Lawrence School.", "Member A"),
    seg(42, 46, "Second the motion. All in favor?", "Chair"),
    seg(48, 55, "The motion carries, unanimous. Maya Okafor will notify the Transportation Board.", "Chair"),
    seg(60, 75, "Moving on, the crosswalk report from the Parks Department is filed for the record.", "Chair"),
]


class TestBrief(unittest.TestCase):
    def test_brief_is_extractive_and_timestamped(self):
        b = brief(MEETING, n=3)
        self.assertTrue(1 <= len(b) <= 3)
        source_text = " ".join(s["text"] for s in MEETING)
        for row in b:
            self.assertIn(row["text"], source_text)   # never paraphrased
            self.assertIsInstance(row["t"], float)

    def test_brief_prefers_the_motion_over_boilerplate(self):
        texts = " ".join(r["text"] for r in brief(MEETING, n=3))
        self.assertIn("2 million", texts)

    def test_empty_meeting(self):
        self.assertEqual(brief([]), [])


class TestEntities(unittest.TestCase):
    def test_buckets(self):
        e = entities(MEETING)
        names = {r["name"] for r in e["people"]}
        self.assertIn("Maya Okafor", names)
        self.assertTrue(any("Harvard Street" in r["name"] for r in e["places"]))
        self.assertTrue(any("Board" in r["name"] or "Department" in r["name"]
                            for r in e["organizations"]))
        self.assertTrue(any("$2 million" in r["name"] for r in e["money"]))

    def test_counts_and_first_mention(self):
        e = entities(MEETING)
        money = e["money"][0]
        self.assertGreaterEqual(money["count"], 1)
        self.assertGreaterEqual(money["t"], 0)


class TestQuestionsAndDecisions(unittest.TestCase):
    def test_questions_typed(self):
        q = questions(MEETING)
        self.assertGreaterEqual(len(q), 2)
        types = {row["type"] for row in q}
        self.assertIn("budget", types)
        self.assertIn("timeline", types)

    def test_decision_carries(self):
        d = decisions(MEETING)
        self.assertTrue(d)
        self.assertEqual(d[0]["outcome"], "passes")


class TestParticipationTopicsCloud(unittest.TestCase):
    def test_participation_shares_sum_to_one(self):
        rows = participation(MEETING)
        self.assertAlmostEqual(sum(r["share"] for r in rows), 1.0, places=2)
        self.assertEqual(rows[0]["speaker"], "Chair")  # most talk time

    def test_wordfreq_filters_stopwords(self):
        wf = word_freq(MEETING)
        words = {w["word"] for w in wf}
        self.assertIn("crosswalk", words)
        self.assertNotIn("the", words)
        self.assertNotIn("motion", words)  # civic stopword

    def test_topics_need_recurrence(self):
        t = topics(MEETING)
        for row in t:
            self.assertGreaterEqual(row["count"], 3)


class TestAsk(unittest.TestCase):
    def test_ask_finds_the_passage(self):
        r = ask(MEETING, "what happened with the crosswalk budget")
        self.assertTrue(r["passages"])
        self.assertTrue(any("2 million" in p["text"] for p in r["passages"]))
        self.assertIsNone(r["note"])

    def test_ask_with_no_content_words(self):
        r = ask(MEETING, "so and the")
        self.assertEqual(r["passages"], [])
        self.assertTrue(r["note"])

    def test_ask_misses_honestly(self):
        r = ask(MEETING, "helicopter zoning xylophone")
        self.assertEqual(r["passages"], [])
        self.assertTrue(r["note"])


if __name__ == "__main__":
    unittest.main()
