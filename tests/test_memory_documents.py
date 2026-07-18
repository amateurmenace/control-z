"""Documents in the record — extraction, chunking, issue assignment, store.

Hermetic: a throwaway corpus, no network, no PDF library required for the store
tests (the extraction tests skip cleanly when pypdf is absent). The document
pipeline's core — chunk, embed, link to issues — is exercised end to end.
"""

import tempfile
import unittest
from pathlib import Path

from memory import documents
from memory.store import Corpus

ZONING = [
    {"start": 0.0, "end": 6.0, "speaker": "Chair",
     "text": "We turn to the Harvard Street rezoning article tonight."},
    {"start": 6.0, "end": 12.0, "speaker": "Member",
     "text": "The MBTA Communities overlay is the heart of the rezoning."},
]


class DocStoreTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-docs-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        self.c.upsert_meeting({"id": "m1", "status": "live", "town": "Brookline",
                               "body": "Select Board", "date": "2026-05-19",
                               "title": "Select Board"})
        self.c.replace_segments("m1", ZONING)

    def tearDown(self):
        self.td.cleanup()

    def test_upsert_and_list_document(self):
        self.c.upsert_document({"id": "doc:a", "meeting_id": "m1",
                                "town": "Brookline", "kind": "Agenda",
                                "title": "Agenda", "date": "2026-05-19",
                                "pages": 3})
        docs = self.c.list_documents(town="Brookline")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["kind"], "Agenda")
        self.assertEqual(self.c.list_documents(meeting_id="m1")[0]["id"], "doc:a")

    def test_chunks_embed_and_roundtrip(self):
        self.c.upsert_document({"id": "doc:a", "meeting_id": "m1",
                                "town": "Brookline", "kind": "Agenda"})
        self.c.replace_doc_chunks("doc:a", [
            {"page": 1, "text": "the harvard street rezoning overlay"},
            {"page": 2, "text": "select board discussion of the article"}])
        chunks = self.c.doc_chunks_of("doc:a")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["page"], 1)
        self.assertEqual(self.c.get_document("doc:a")["n_chunks"], 2)

    def test_assign_document_links_by_keyword(self):
        # an issue whose keyword the document names
        self.c.upsert_issue({"id": "issue:brookline:rezoning", "town": "Brookline",
                             "name": "Rezoning", "status": "active",
                             "keywords": ["rezoning"], "origin": "auto"})
        self.c.upsert_document({"id": "doc:a", "meeting_id": "m1",
                                "town": "Brookline", "kind": "Agenda"})
        self.c.replace_doc_chunks("doc:a", [
            {"page": 4, "text": "public hearing on the harvard street rezoning"},
            {"page": 5, "text": "unrelated boilerplate about parking permits"}])
        res = documents.assign_document(self.c, "doc:a")
        self.assertGreaterEqual(res["linked"], 1)
        paper = self.c.issue_paper("issue:brookline:rezoning")
        self.assertEqual(len(paper), 1)
        self.assertEqual(paper[0]["doc_id"], "doc:a")
        # the cited chunk carries its page number — a real citation
        self.assertEqual(paper[0]["cites"][0]["page"], 4)

    def test_forget_document_cascades(self):
        self.c.upsert_issue({"id": "issue:x", "town": "Brookline", "name": "X",
                             "status": "active", "keywords": ["rezoning"]})
        self.c.upsert_document({"id": "doc:a", "meeting_id": "m1",
                                "town": "Brookline"})
        self.c.replace_doc_chunks("doc:a", [{"page": 1, "text": "rezoning"}])
        documents.assign_document(self.c, "doc:a")
        self.assertTrue(self.c.forget_document("doc:a"))
        self.assertEqual(self.c.list_documents(), [])
        self.assertEqual(self.c.doc_chunks_of("doc:a"), [])
        self.assertEqual(self.c.issue_paper("issue:x"), [])

    def test_forget_meeting_takes_its_paper(self):
        self.c.upsert_document({"id": "doc:a", "meeting_id": "m1",
                                "town": "Brookline"})
        self.c.replace_doc_chunks("doc:a", [{"page": 1, "text": "hi"}])
        self.c.forget("m1")
        self.assertEqual(self.c.list_documents(), [])


class ExtractTest(unittest.TestCase):
    def test_chunk_pages_carries_page_numbers(self):
        pages = ["one two three four five six seven eight nine ten",
                 "", "alpha beta gamma delta epsilon zeta eta theta iota kappa"]
        chunks = documents.chunk_pages(pages, words=10)
        self.assertTrue(all("page" in c and "text" in c for c in chunks))
        # page 2 is empty, so no chunk claims it; page 3 chunks say page 3
        pages_seen = {c["page"] for c in chunks}
        self.assertIn(1, pages_seen)
        self.assertIn(3, pages_seen)
        self.assertNotIn(2, pages_seen)

    def test_available_reports_pypdf(self):
        # available() is a truthful probe either way — it never raises
        self.assertIsInstance(documents.available(), bool)

    def test_extract_pages_when_pypdf_present(self):
        if not documents.available():
            self.skipTest("pypdf not installed")
        # a minimal one-page PDF built by pypdf itself
        import pypdf
        w = pypdf.PdfWriter()
        w.add_blank_page(width=200, height=200)
        import io
        buf = io.BytesIO()
        w.write(buf)
        pages = documents.extract_pages(buf.getvalue())
        self.assertEqual(len(pages), 1)   # one page in, one string out


if __name__ == "__main__":
    unittest.main()
