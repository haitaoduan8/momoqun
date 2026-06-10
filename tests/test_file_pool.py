"""file_pool 多机文件分配测试。"""

import os
import shutil
import tempfile
import unittest

from data import file_pool


class FilePoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.accounts_dir = os.path.join(self.tmp, "accounts")
        os.makedirs(self.accounts_dir, exist_ok=True)
        self.pool_backup = file_pool._POOL_PATH
        file_pool._POOL_PATH = os.path.join(self.tmp, "file_pool.json")

    def tearDown(self) -> None:
        file_pool._POOL_PATH = self.pool_backup
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, name: str) -> str:
        path = os.path.join(self.accounts_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(name)
        return path

    def test_claim_skips_used_files(self) -> None:
        self._touch("a.dat")
        self._touch("b.dat")
        p1, err1 = file_pool.claim_next_file(self.accounts_dir, "dev_a")
        p2, err2 = file_pool.claim_next_file(self.accounts_dir, "dev_b")
        p3, err3 = file_pool.claim_next_file(self.accounts_dir, "dev_c")
        self.assertEqual(err1, "")
        self.assertEqual(err2, "")
        self.assertTrue(p1 and p2)
        self.assertIsNone(p3)
        self.assertIn("无可用", err3)
        status = file_pool.get_pool_status(self.accounts_dir)
        self.assertEqual(status["used_count"], 2)
        self.assertEqual(status["remaining"], 0)


if __name__ == "__main__":
    unittest.main()
