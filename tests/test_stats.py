import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("stats", Path(__file__).resolve().parents[1] / "scripts/update_stats.py")
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


class StatsTests(unittest.TestCase):
    def test_chart_proportions_and_escaping(self):
        svg = stats.chart({"Python": 75, "C<&": 25})
        root = ET.fromstring(svg)
        bars = root.findall('{http://www.w3.org/2000/svg}rect')[1:]
        self.assertEqual([float(bar.attrib['width']) for bar in bars], [450, 150])
        self.assertIn('75.0%', svg)
        self.assertIn('25.0%', svg)
        self.assertIn('C&lt;&amp;', svg)

    def test_pagination_filters_and_zero_prs(self):
        calls = []

        def fetch(path):
            calls.append(path)
            if path.startswith("users/") and "&page=1" in path:
                return [{"name": "fork", "fork": True, "archived": False}] * 97 + [
                    {"name": "old", "fork": False, "archived": True},
                    {"name": "altsun", "fork": False, "archived": False},
                    {"name": "tool", "fork": False, "archived": False}]
            if path.startswith("users/") and "&page=2" in path:
                return [{"name": "second", "fork": False, "archived": False}]
            if path.endswith("/languages"):
                return {"Python": 30, "Common Lisp": 10}
            return {"incomplete_results": False, "total_count": 0}

        languages, merged = stats.collect(fetch)
        self.assertEqual(languages, {"Python": 60, "Common Lisp": 20})
        body = stats.render(languages, merged)
        self.assertIn("75.0%", body)
        self.assertIn("25.0%", body)
        self.assertIn("0 merged pull requests", body)
        self.assertEqual(len(calls), 5)

    def test_markers_and_empty_data(self):
        text = f"before\n{stats.START}\nold\n{stats.END}\nafter"
        result = stats.replace_stats(text, stats.render({}, 0))
        self.assertTrue(result.startswith("before\n" + stats.START))
        self.assertTrue(result.endswith(stats.END + "\nafter"))
        self.assertIn("No language data", result)
        with self.assertRaises(ValueError):
            stats.replace_stats("missing markers", "new")
        with self.assertRaises(ValueError):
            stats.replace_stats(stats.END + stats.START, "new")

    def test_api_failure_preserves_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            path.write_text("original", encoding="utf-8")
            with patch.object(stats, "README", path), patch.object(stats, "collect", side_effect=RuntimeError("API failed")):
                with self.assertRaises(RuntimeError):
                    stats.main()
            self.assertEqual(path.read_text(encoding="utf-8"), "original")

    def test_incomplete_search_fails(self):
        with self.assertRaises(RuntimeError):
            stats.collect(lambda path: [] if path.startswith("users/") else {"incomplete_results": True})


if __name__ == "__main__":
    unittest.main()
