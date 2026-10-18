import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pull_available_models as generator
from providers import PROVIDERS, REVIEW_DATE, SECTIONS


class CatalogTests(unittest.TestCase):
    def test_only_explicit_zero_input_and_output_prices_qualify(self):
        cases = [
            ("valid:free", {"prompt": "0", "completion": "0.0"}),
            ("paid:free", {"prompt": "0", "completion": "0.01"}),
            ("missing:free", {"prompt": "0"}),
            ("invalid:free", {"prompt": "unknown", "completion": "0"}),
            ("nan:free", {"prompt": "NaN", "completion": "0"}),
            ("negative:free", {"prompt": "-1", "completion": "1"}),
            ("not-free", {"prompt": "0", "completion": "0"}),
            ("not-free:free-preview", {"prompt": "0", "completion": "0"}),
        ]
        payload = {"data": [{"id": model_id, "pricing": pricing} for model_id, pricing in cases]}
        models = generator.select_free_models(payload)
        self.assertEqual([model["id"] for model in models], ["valid:free"])

    def test_failed_or_empty_refresh_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            original = '{"retrieved_at": "old", "models": []}\n'
            path.write_text(original)
            with patch.object(generator, "urlopen", side_effect=URLError("offline")):
                with self.assertRaises(URLError):
                    generator.fetch_catalog()
            self.assertEqual(path.read_text(), original)
            with patch.object(generator, "urlopen", return_value=io.StringIO('{"data": []}')):
                with self.assertRaises(ValueError):
                    generator.fetch_catalog()
            self.assertEqual(path.read_text(), original)

    def test_fetch_returns_metadata_without_reclassifying_offers(self):
        payload = {"data": [{"id": "example:free", "name": "Example", "pricing": {"prompt": "0", "completion": "0"}}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            with patch.object(generator, "urlopen", return_value=io.StringIO(json.dumps(payload))):
                snapshot = generator.fetch_catalog()
            self.assertFalse(path.exists())
            self.assertEqual(snapshot["models"][0]["id"], "example:free")
            self.assertEqual(generator.REVIEW_DATE, REVIEW_DATE)


class ReadmeTests(unittest.TestCase):
    def test_every_provider_has_a_unique_id_category_and_official_source(self):
        self.assertEqual(len(PROVIDERS), len({provider["id"] for provider in PROVIDERS}))
        for provider in PROVIDERS:
            with self.subTest(provider=provider["id"]):
                self.assertIn(provider["category"], SECTIONS)
                self.assertTrue(provider["sources"])
                self.assertTrue(all(url.startswith("https://") for _, url in provider["sources"]))

    def test_retired_and_trial_services_never_appear_as_free(self):
        categories = {provider["id"]: provider["category"] for provider in PROVIDERS}
        for provider in ("github", "together", "sambanova", "huggingface"):
            self.assertEqual(categories[provider], "paid")
        for provider in ("cerebras", "xiaomi", "alibaba", "vertex"):
            self.assertEqual(categories[provider], "trial")
        self.assertEqual(categories["modal"], "compute")
        self.assertEqual(categories["zai"], "free")

    def test_huggingface_review_does_not_redate_other_offers(self):
        huggingface = next(provider for provider in PROVIDERS if provider["id"] == "huggingface")
        self.assertEqual(huggingface["reviewed_on"], "2026-10-18")
        self.assertIn("no monthly", huggingface["offer"])
        self.assertEqual(REVIEW_DATE, "2026-10-03")
        for provider in PROVIDERS:
            if provider["id"] != "huggingface":
                self.assertEqual(provider.get("reviewed_on", REVIEW_DATE), "2026-10-03")

    def test_render_is_offline_deterministic_and_complete(self):
        template = (generator.SCRIPT_DIR / "README_template.md").read_text()
        snapshot = {"retrieved_at": "2026-10-01T00:00:00+00:00", "models": []}
        with patch.object(generator, "urlopen", side_effect=AssertionError("Unexpected network call")):
            first = generator.render_readme(template, snapshot)
            second = generator.render_readme(template, snapshot)
        self.assertEqual(first, second)
        self.assertNotIn("{{", first)
        self.assertIn(f"Provider offers reviewed: {REVIEW_DATE}", first)
        self.assertIn(snapshot["retrieved_at"], first)
        for provider in PROVIDERS:
            self.assertEqual(first.count(f"### [{provider['name']}]"), 1)

    def test_table_of_contents_links_match_generated_headings(self):
        template = (generator.SCRIPT_DIR / "README_template.md").read_text()
        readme = generator.render_readme(template)
        anchors = []
        for title in re.findall(r"^#{2,3} (.+)", readme, re.MULTILINE):
            display = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", title)
            anchors.append(re.sub(r"[^a-z0-9 _-]", "", display.lower()).replace(" ", "-"))
        toc_targets = re.findall(r"^\s*- \[.*?\]\(#(.*?)\)$", readme, re.MULTILINE)
        self.assertEqual(toc_targets, anchors)
        self.assertEqual(len(anchors), len(set(anchors)))


class OutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.src = self.root / "src"
        self.src.mkdir()
        self.catalog = self.src / "openrouter_models.json"
        self.readme = self.root / "README.md"
        self.template = self.src / "README_template.md"
        self.template.write_text("{{REVIEW_DATE}}\n{{TOC}}\n{{PROVIDER_SECTIONS}}\n")
        self.old_catalog = '{"retrieved_at": "old", "models": []}\n'
        self.catalog.write_text(self.old_catalog)
        self.readme.write_text("old readme\n")
        self.payload = {"data": [{"id": "example:free", "name": "Example", "pricing": {"prompt": "0", "completion": "0"}}]}

    def run_refresh(self):
        with patch.object(generator, "SCRIPT_DIR", self.src), \
             patch.object(generator, "CATALOG_PATH", self.catalog), \
             patch.object(generator, "urlopen", return_value=io.StringIO(json.dumps(self.payload))), \
             patch.object(sys, "argv", ["generator", "--refresh-models"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            generator.main()

    def assert_old_outputs(self):
        self.assertEqual(self.catalog.read_text(), self.old_catalog)
        self.assertEqual(self.readme.read_text(), "old readme\n")
        self.assertEqual(list(self.root.rglob(".readme-*")), [])

    def test_missing_template_preserves_both_outputs(self):
        self.template.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_refresh()
        self.assert_old_outputs()

    def test_render_failure_preserves_both_outputs(self):
        with patch.object(generator, "render_readme", side_effect=ValueError("render failed")):
            with self.assertRaises(ValueError):
                self.run_refresh()
        self.assert_old_outputs()

    def test_empty_catalog_preserves_both_outputs(self):
        self.payload = {"data": []}
        with self.assertRaises(ValueError):
            self.run_refresh()
        self.assert_old_outputs()

    def test_second_staging_write_failure_preserves_both_outputs(self):
        original_write = Path.write_text

        def fail_readme_stage(path, text, *args, **kwargs):
            if path.name == "new" and path.parent.parent == self.root:
                raise OSError("cannot stage README")
            return original_write(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", fail_readme_stage):
            with self.assertRaises(OSError):
                self.run_refresh()
        self.assert_old_outputs()

    def test_first_replace_failure_preserves_both_outputs(self):
        with patch.object(Path, "replace", side_effect=OSError("cannot replace catalog")):
            with self.assertRaises(OSError):
                self.run_refresh()
        self.assert_old_outputs()

    def test_second_replace_failure_restores_previous_catalog(self):
        original_replace = Path.replace

        def fail_readme_replace(path, target):
            if target == self.readme:
                raise OSError("cannot replace README")
            return original_replace(path, target)

        with patch.object(Path, "replace", fail_readme_replace):
            with self.assertRaises(OSError):
                self.run_refresh()
        self.assert_old_outputs()

    def test_second_replace_failure_removes_new_catalog_if_none_existed(self):
        self.catalog.unlink()
        original_replace = Path.replace

        def fail_readme_replace(path, target):
            if target == self.readme:
                raise OSError("cannot replace README")
            return original_replace(path, target)

        with patch.object(Path, "replace", fail_readme_replace):
            with self.assertRaises(OSError):
                self.run_refresh()
        self.assertFalse(self.catalog.exists())
        self.assertEqual(self.readme.read_text(), "old readme\n")
        self.assertEqual(list(self.root.rglob(".readme-*")), [])

    def test_rollback_failure_retains_recovery_files_and_reports_them(self):
        original_replace = Path.replace

        def fail_readme_and_rollback(path, target):
            if target == self.readme or path.name == "old":
                raise OSError("simulated filesystem failure")
            return original_replace(path, target)

        with patch.object(Path, "replace", fail_readme_and_rollback):
            with self.assertRaisesRegex(RuntimeError, "recovery files retained") as failure:
                self.run_refresh()
        backups = list(self.src.glob(".readme-*/old"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), self.old_catalog)
        self.assertIn(str(backups[0].parent), str(failure.exception))
        self.assertEqual(self.readme.read_text(), "old readme\n")

    def test_successful_refresh_updates_both_outputs_consistently(self):
        self.run_refresh()
        snapshot = json.loads(self.catalog.read_text())
        self.assertEqual(snapshot["models"][0]["id"], "example:free")
        self.assertEqual(self.readme.read_text(), generator.render_readme(self.template.read_text(), snapshot))
        self.assertEqual(list(self.root.rglob(".readme-*")), [])


if __name__ == "__main__":
    unittest.main()
