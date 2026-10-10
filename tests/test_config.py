import json
import tempfile
import unittest
from pathlib import Path

from kobo2mail.__main__ import main
from kobo2mail.config import ConfigError, form_config, load_config

ROOT = Path(__file__).resolve().parent.parent


class ConfigTest(unittest.TestCase):
    def write(self, data):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(data, tmp)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_per_form_override_merges(self):
        path = self.write({"forms": {
            "default": {"brand_color": "#111", "labels": {"a": "A"}, "include": ["*"]},
            "uid1": {"brand_color": "#222", "labels": {"b": "B"}, "include": ["x/*"]},
        }})
        config = load_config(path)
        resolved = form_config(config, {"_xform_id_string": "uid1"})
        self.assertEqual(resolved["brand_color"], "#222")
        self.assertEqual(resolved["labels"], {"a": "A", "b": "B"})
        self.assertEqual(resolved["include"], ["x/*"])
        other = form_config(config, {"_xform_id_string": "uid2"})
        self.assertEqual(other["brand_color"], "#111")

    def test_invalid_provider(self):
        with self.assertRaises(ConfigError):
            load_config(self.write({"provider": "pigeon"}))

    def test_invalid_include(self):
        with self.assertRaises(ConfigError):
            load_config(self.write({"forms": {"default": {"include": "*"}}}))

    def test_shipped_configs_load(self):
        for name in ("config.json", "config.example.json"):
            load_config(ROOT / name)


class CliTest(unittest.TestCase):
    def test_dispatch_event_dry_run(self):
        sub = json.loads((ROOT / "examples" / "sample_submission.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"action": "kobo_submission",
                                         "client_payload": {"submission": sub}}), encoding="utf-8")
            code = main(["--event", str(event), "--config", str(ROOT / "config.json"), "--dry-run"])
        self.assertEqual(code, 0)

    def test_no_recipient_is_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "sub.json"
            sub.write_text(json.dumps({"_id": 1, "contact/name": "x"}), encoding="utf-8")
            code = main(["--submission", str(sub), "--config", str(ROOT / "config.json")])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
