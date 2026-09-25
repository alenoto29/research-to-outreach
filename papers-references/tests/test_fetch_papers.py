import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_papers.py"
SPEC = importlib.util.spec_from_file_location("fetch_papers", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FetchStatusTests(unittest.TestCase):
    def test_empty_result_is_distinct_from_fetch_failure(self):
        self.assertEqual(module.source_status([]), {"status": "empty", "count": 0})
        self.assertEqual(module.source_status([], "request_failed"),
                         {"status": "error", "error": "request_failed", "count": 0})
        self.assertEqual(module.source_status([{"title": "synthetic"}]),
                         {"status": "results", "count": 1})

    def test_cli_refuses_network_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "papers"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "synthetic topic", "--out", str(out)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("pass --allow-network", result.stderr)
            self.assertFalse(out.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
