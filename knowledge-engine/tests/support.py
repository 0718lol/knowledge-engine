import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATA_DIR = Path(self.temp_dir.name)
        database.DB_PATH = database.DATA_DIR / "test.db"
        database.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def seed(self):
        import seed

        with contextlib.redirect_stdout(io.StringIO()):
            seed.seed()
