from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from output_files import atomic_text, plan_exports


class ExportSafety(unittest.TestCase):
    def test_failed_write_leaves_original(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "Wait.anim"
            with atomic_text(path) as stream:
                stream.write("old")
            with self.assertRaises(ValueError), atomic_text(path) as stream:
                stream.write("partial")
                raise ValueError()
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_batch_names(self):
        for bad in ["../outside", "CON", "A:stream", "end.", "", "a/b"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                plan_exports([("Rig|Walk", bad)], ".")
        with self.assertRaises(ValueError):
            plan_exports([("A|Run", "Run"), ("B|Run", "run")], ".")
        self.assertEqual(plan_exports([("Rig|Walk", "Walk")], ".")[0][0], "Rig|Walk")
