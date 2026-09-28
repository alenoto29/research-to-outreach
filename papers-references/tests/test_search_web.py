import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search_web.py"
spec = importlib.util.spec_from_file_location("search_web", SCRIPT)
search_web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_web)


class SearchWebTests(unittest.TestCase):
    def test_missing_key_never_calls_network(self):
        with patch.object(search_web.urllib.request, "urlopen") as fetch:
            with self.assertRaisesRegex(ValueError, "SERPER_API_KEY"):
                search_web.search("topic", "")
            fetch.assert_not_called()

    def test_results_are_normalized_and_key_is_not_in_output(self):
        response = io.BytesIO(json.dumps({"organic": [
            {"title": "Title", "link": "https://example.org/story", "snippet": "A lead"},
            {"title": "No URL", "link": "javascript:alert(1)"},
            {"title": "No host", "link": "https:///story"},
        ]}).encode("utf-8"))
        with patch.object(search_web.urllib.request, "urlopen", return_value=response) as fetch:
            result = search_web.search("energy research", "private-key", 5)
        request = fetch.call_args.args[0]
        self.assertEqual(request.get_header("X-api-key"), "private-key")
        self.assertEqual(json.loads(request.data), {"q": "energy research", "num": 5})
        self.assertEqual(result["results"], [
            {"title": "Title", "url": "https://example.org/story", "snippet": "A lead"}
        ])
        self.assertNotIn("private-key", json.dumps(result))

    def test_empty_and_invalid_response_are_different(self):
        with patch.object(search_web.urllib.request, "urlopen", return_value=io.BytesIO(b'{"organic": []}')):
            self.assertEqual(search_web.search("topic", "key")["status"], "empty")
        with patch.object(search_web.urllib.request, "urlopen", return_value=io.BytesIO(b'{}')):
            with self.assertRaisesRegex(ValueError, "organic"):
                search_web.search("topic", "key")
        with patch.object(search_web.urllib.request, "urlopen", return_value=io.BytesIO(b'{not json')):
            with self.assertRaises(json.JSONDecodeError):
                search_web.search("topic", "key")


if __name__ == "__main__":
    unittest.main()
