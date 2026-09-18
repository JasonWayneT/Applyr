"""Export of adjudication marks cannot write blank your_mark rows. FR-327."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_stage0_adjudication as export_mod


def _write_extract(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["slug", "item_id", "line", "source", "your_mark"],
        )
        writer.writeheader()
        writer.writerows(rows)


class ExportStage0AdjudicationTests(unittest.TestCase):
    def test_blank_mark_in_write_set_hard_fails(self) -> None:
        with self.assertRaises(export_mod.BlankMarkExportError):
            export_mod.approved_rows_from_marks(
                [{"item_id": "actblue:e7", "line": "SQL is a plus", "slug": "actblue",
                  "source": "jason", "your_mark": ""}],
                reviewed_by="jason",
                reviewed_at="2026-09-17T00:00:00+00:00",
                out_name="training_data_approved.csv",
            )

    def test_marked_count_equals_written_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "extract.csv"
            out = Path(tmp) / "approved.csv"
            _write_extract(extract, [
                {"slug": "actblue", "item_id": "actblue:e7", "line": "SQL is a plus",
                 "source": "jason", "your_mark": "preferred"},
                {"slug": "actblue", "item_id": "actblue:e0", "line": "Title chrome",
                 "source": "agy", "your_mark": ""},
                {"slug": "acquia", "item_id": "acquia:e6", "line": "Curiosity",
                 "source": "claude_review", "your_mark": ""},
            ])
            written = export_mod.export_approved(
                extract, out, reviewed_by="jason", reviewed_at="2026-09-17T00:00:00+00:00"
            )
            self.assertEqual(len(written), 1)
            with out.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "preferred")
            self.assertEqual(rows[0]["reviewed_by"], "jason")
            self.assertNotIn("", {row["label"] for row in rows})

    def test_claude_review_source_cannot_export_even_when_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "extract.csv"
            out = Path(tmp) / "approved.csv"
            _write_extract(extract, [
                {"slug": "actblue", "item_id": "actblue:e7", "line": "SQL is a plus",
                 "source": "jason", "your_mark": "preferred"},
                {"slug": "acquia", "item_id": "acquia:e1", "line": "Grow your career here",
                 "source": "claude_review", "your_mark": "junk"},
            ])
            written = export_mod.export_approved(
                extract, out, reviewed_by="jason", reviewed_at="2026-09-17T00:00:00+00:00"
            )
            self.assertEqual(len(written), 1)
            self.assertEqual(written[0]["source_file"], "actblue:e7")
            with out.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["source_file"] for row in rows], ["actblue:e7"])
            self.assertNotIn("claude_review", {row["suggestion_source"] for row in rows})

    def test_approved_rows_reject_non_jason_source(self) -> None:
        with self.assertRaises(export_mod.NonJasonSourceExportError):
            export_mod.approved_rows_from_marks(
                [{"item_id": "acquia:e1", "line": "Grow your career here", "slug": "acquia",
                  "source": "claude_review", "your_mark": "junk"}],
                reviewed_by="jason",
                reviewed_at="2026-09-17T00:00:00+00:00",
                out_name="training_data_approved.csv",
            )

    def test_export_approved_many_merges_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.csv"
            second = Path(tmp) / "b.csv"
            out = Path(tmp) / "approved.csv"
            _write_extract(first, [
                {"slug": "actblue", "item_id": "actblue:e2", "line": "FHIR knowledge",
                 "source": "jason", "your_mark": "required"},
            ])
            _write_extract(second, [
                {"slug": "eso", "item_id": "eso:e1", "line": "CSPO is a plus",
                 "source": "claude_opus_jason_approved", "your_mark": "preferred"},
            ])
            written = export_mod.export_approved_many(
                [first, second], out, reviewed_by="jason",
                reviewed_at="2026-09-17T00:00:00+00:00",
            )
            self.assertEqual(len(written), 2)
            sources = {row["suggestion_source"] for row in written}
            self.assertEqual(sources, {"jason", "claude_opus_jason_approved"})

    def test_claude_opus_jason_approved_can_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "extract.csv"
            out = Path(tmp) / "approved.csv"
            _write_extract(extract, [
                {"slug": "actblue", "item_id": "actblue:e2", "line": "FHIR knowledge",
                 "source": "claude_opus_jason_approved", "your_mark": "required"},
            ])
            written = export_mod.export_approved(
                extract, out, reviewed_by="jason", reviewed_at="2026-09-17T00:00:00+00:00"
            )
            self.assertEqual(len(written), 1)
            self.assertEqual(written[0]["suggestion_source"], "claude_opus_jason_approved")
            self.assertEqual(written[0]["reviewed_by"], "jason")

    def test_promote_claude_review_only_rewrites_filled_marks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "extract.csv"
            _write_extract(extract, [
                {"slug": "actblue", "item_id": "actblue:e2", "line": "FHIR knowledge",
                 "source": "claude_review", "your_mark": "required"},
                {"slug": "actblue", "item_id": "actblue:e3", "line": "unmarked leftover",
                 "source": "claude_review", "your_mark": ""},
                {"slug": "eso", "item_id": "eso:s1", "line": "skip row",
                 "source": "jason", "your_mark": "SKIP"},
            ])
            changed = export_mod.promote_claude_review_marks(extract)
            self.assertEqual(changed, 1)
            with extract.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            by_id = {row["item_id"]: row for row in rows}
            self.assertEqual(by_id["actblue:e2"]["source"], "claude_opus_jason_approved")
            self.assertEqual(by_id["actblue:e3"]["source"], "claude_review")
            self.assertEqual(by_id["eso:s1"]["source"], "jason")

    def test_claude_reviewer_cannot_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "extract.csv"
            out = Path(tmp) / "approved.csv"
            _write_extract(extract, [
                {"slug": "actblue", "item_id": "actblue:e7", "line": "SQL is a plus",
                 "source": "jason", "your_mark": "preferred"},
            ])
            with self.assertRaisesRegex(ValueError, "human reviewed_by"):
                export_mod.export_approved(extract, out, reviewed_by="claude_review")


if __name__ == "__main__":
    unittest.main()
