"""StorageHandler 路径与计数测试。"""

import os
import tempfile
import unittest

from data import storage as storage_mod


class StoragePathTests(unittest.TestCase):
    def test_sanitize_serial(self) -> None:
        self.assertEqual(storage_mod._sanitize_serial("127.0.0.1:5555"), "127.0.0.1_5555")
        self.assertEqual(storage_mod._sanitize_serial(None), "default")
        self.assertEqual(storage_mod._sanitize_serial("  "), "default")

    def test_friends_path_for(self) -> None:
        path = storage_mod.friends_path_for("127.0.0.1:5555")
        self.assertTrue(path.endswith(os.path.join("friends", "127.0.0.1_5555.json")))


class StorageHandlerTests(unittest.TestCase):
    def test_count_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orig_dir = storage_mod._FRIENDS_DIR
            storage_mod._FRIENDS_DIR = tmp
            try:
                h = storage_mod.StorageHandler(serial="test-device")
                h.upsert("u1", {"uid": "u1", "name": "A", "status": "pending"})
                h.upsert("u2", {"uid": "u2", "name": "B", "status": "mutual"})
                counts = h.count_by_status()
                self.assertEqual(counts.get("total"), 2)
                self.assertEqual(counts.get("pending"), 1)
                self.assertEqual(counts.get("mutual"), 1)
            finally:
                storage_mod._FRIENDS_DIR = orig_dir


if __name__ == "__main__":
    unittest.main()
