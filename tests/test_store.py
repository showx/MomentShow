from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from momentshow.store import connect, count_moments, insert_moment, list_authors, list_moments


class StoreTests(unittest.TestCase):
    def test_insert_and_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "moments.db"
            conn = connect(db)
            first = insert_moment(
                conn,
                author="Alice",
                time_text="刚刚",
                body="hello",
                raw_text="Alice\nhello\n刚刚",
                content_hash="abc",
            )
            second = insert_moment(
                conn,
                author="Alice",
                time_text="刚刚",
                body="hello",
                raw_text="Alice\nhello\n刚刚",
                content_hash="abc",
            )
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(count_moments(conn), 1)
            self.assertEqual(list_authors(conn), ["Alice"])
            self.assertEqual(list_moments(conn)[0].body, "hello")
            conn.close()


if __name__ == "__main__":
    unittest.main()
