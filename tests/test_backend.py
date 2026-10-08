import base64
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.codec import decode_filter, fields
from backend.generator import Generator
from backend.providers import (CATALOG_URL, GAME_URL, PROFILE_URL, LiteralParser,
                               normalize_profile, parse_catalog_chunk, resolve_planner, validate_url)
from backend.service import LootService
from backend.vendor import d4_lootfilter as native

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "maxroll-profile.json").read_text())
MAPPING = json.loads((FIXTURES / "maxroll-affixes.json").read_text())
CHUNK = (FIXTURES / "catalog-chunk.js").read_text()


class FakeClient:
    def __init__(self):
        self.offline = False

    def text(self, url):
        if self.offline:
            raise ValueError("Offline")
        if url == CATALOG_URL:
            return '<script src="/_next/static/changed-hash.js"></script>'
        if url.endswith("changed-hash.js"):
            return CHUNK
        if "/build-guides/" in url:
            return '<a href="https://maxroll.gg/d4/planner/nq4dbn0q">Planner</a>'
        raise AssertionError(url)

    def json(self, url):
        if self.offline:
            raise ValueError("Offline")
        if url == PROFILE_URL.format("nq4dbn0q"):
            return copy.deepcopy(PROFILE)
        if url == GAME_URL:
            return {"affixes": {sno: {"id": int(nid)} for nid, sno in MAPPING.items()}, "version": "fixture"}
        raise AssertionError(url)


class ProvidersTest(unittest.TestCase):
    def test_real_catalogue_literal_excerpt(self):
        records = parse_catalog_chunk(CHUNK)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["className"], "Sorcerer")
        self.assertEqual(decode_filter(records[0]["importCode"])["ruleCount"], 17)

    def test_literal_parser_rejects_executable_expressions(self):
        with self.assertRaises(ValueError):
            LiteralParser('{id:"x",payload:fetch("https://example.org")}').value()
        parsed = LiteralParser(r'{id:"a",enabled:!0,items:[1,null],label:"End\x20game"}').value()
        self.assertEqual(parsed["label"], "End game")
        self.assertTrue(parsed["enabled"])

    def test_exact_hosts_and_paths_only(self):
        for url in ["http://maxroll.gg/d4/planner/abcd", "https://maxroll.gg.evil.test/d4/planner/abcd",
                    "https://maxroll.gg@127.0.0.1/", "https://maxroll.gg:8080/", "file:///etc/passwd"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        self.assertEqual(resolve_planner(FakeClient(), "https://maxroll.gg/d4/planner/nq4dbn0q"), "nq4dbn0q")
        self.assertEqual(resolve_planner(FakeClient(), "https://maxroll.gg/d4/build-guides/rain-of-arrows-rogue-guide"), "nq4dbn0q")
        with self.assertRaises(ValueError):
            resolve_planner(FakeClient(), "https://maxroll.gg/d4/planner/builds")

    def test_current_maxroll_schema_and_embedded_filters(self):
        profile = normalize_profile(PROFILE)
        self.assertEqual(len(profile["data"]["profiles"]), 8)
        self.assertEqual(len(profile["data"]["lootFilters"]), 3)
        self.assertEqual(profile["cls"], "rogue")
        for record in profile["data"]["lootFilters"][:2]:
            self.assertLessEqual(decode_filter(record["code"])["ruleCount"], 25)
        # The actual published Strict field contains two concatenated base64
        # messages. Keep that fixture so malformed provider codes stay excluded.
        with self.assertRaises(ValueError):
            decode_filter(profile["data"]["lootFilters"][2]["code"])


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = Generator()

    def fixture(self):
        return normalize_profile(copy.deepcopy(PROFILE))

    def test_all_live_variants_generate_highlight_only(self):
        build = self.fixture()
        for index in range(len(build["data"]["profiles"])):
            with self.subTest(variant=index):
                code, preview, notes = self.generator.generate(build, index, MAPPING)
                self.assertTrue(code)
                self.assertNotIn("Hide", [r["action"] for r in preview["rules"]])
                self.assertLessEqual(preview["ruleCount"], 25)
                self.assertIn("Keep Uniques", [r["name"] for r in preview["rules"]])
                self.assertTrue(all("kept visible" in note for note in notes))

    def test_tempering_cannot_change_the_filter(self):
        build = self.fixture()
        before = self.generator.generate(build, 1, MAPPING)[0]
        for item in build["data"]["items"].values():
            item["tempered"] = [{"nid": 999999999, "greater": True}]
        after = self.generator.generate(build, 1, MAPPING)[0]
        self.assertEqual(before, after)

    def test_unknown_affix_is_reported_and_strict_is_rejected(self):
        build = self.fixture()
        item_id = build["data"]["profiles"][1]["items"]["10"]
        build["data"]["items"][str(item_id)]["explicits"].append({"nid": 999999999})
        _, _, notes = self.generator.generate(build, 1, MAPPING)
        self.assertTrue(any("999999999" in note for note in notes))
        with self.assertRaisesRegex(ValueError, "complete mappings"):
            self.generator.generate(build, 1, MAPPING, strict=True)

    def test_fully_mapped_strict_filter_preserves_uniques(self):
        affix = next(iter(self.generator.affixes.by_hash))
        build = {"name": "Test", "data": {"profiles": [{"name": "Endgame", "items": {"4": 1}}],
                 "items": {"1": {"id": "Helm_Legendary_Generic_001", "explicits": [{"nid": affix}]}}}}
        _, preview, notes = self.generator.generate(build, 0, {}, strict=True)
        self.assertFalse(notes)
        self.assertEqual(preview["rules"][-1]["name"], "Hide Junk Gear")
        names = [r["name"] for r in preview["rules"]]
        self.assertLess(names.index("Keep Uniques"), names.index("Hide Junk Gear"))
        self.assertIn("Rare", preview["rules"][-1]["conditions"][0])
        self.assertNotIn("Unique", preview["rules"][-1]["conditions"][0])

    def test_invalid_variant_never_falls_back_silently(self):
        for variant in [-1, 999, "2", True]:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.generator.generate(self.fixture(), variant, MAPPING)

    def test_rule_budget_drops_bis_before_essential_rules(self):
        rules = [{"label": str(i), "type_ids": [1], "ids": [1], "ga": [1], "n_bis": 1, "n_fix": 1} for i in range(15)]
        code, count, dropped = native.build_filter_code("Budget", [], rules, hide_junk=True)
        preview = decode_filter(code)
        self.assertEqual(count, 25)
        self.assertGreater(len(dropped), 0)
        self.assertEqual(sum(r["name"].startswith("Gear:") for r in preview["rules"]), 15)
        self.assertEqual(preview["rules"][-1]["name"], "Hide Junk Gear")


class CodecTest(unittest.TestCase):
    def test_rejects_invalid_codes_and_rule_counts(self):
        for code in ["not a code", "", base64.b64encode(b"\x0a\xff").decode(),
                     base64.b64encode(native._filter_bytes("Empty", [])).decode()]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                decode_filter(code)
        code = base64.b64encode(native._filter_bytes("Too many", [native._rule("Keep", 0, [])] * 26)).decode()
        with self.assertRaises(ValueError):
            decode_filter(code)

    def test_real_code_round_trip_does_not_modify_bytes(self):
        record = parse_catalog_chunk(CHUNK)[0]
        code = record["importCode"]
        decoded = decode_filter(code)
        top = list(fields(base64.b64decode(code)))
        self.assertEqual(len(decoded["rules"]), sum(n == 1 and w == 2 for n, w, _ in top))
        self.assertEqual(record["importCode"], code)


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.service = LootService(self.temp.name, self.client)

    def tearDown(self):
        self.temp.cleanup()

    def test_catalogue_refresh_failure_preserves_original_codes(self):
        result = self.service.list_filters(True)
        self.assertEqual(len(result["filters"]), 3)
        self.assertFalse(result["stale"])
        first = self.service.get_filter(result["filters"][0]["id"])
        self.assertEqual(first["code"], parse_catalog_chunk(CHUNK)[0]["importCode"])
        self.client.offline = True
        cached = self.service.list_filters(True)
        self.assertTrue(cached["stale"])
        self.assertEqual(cached["filters"], result["filters"])

    def test_first_run_offline_still_allows_empty_view(self):
        self.client.offline = True
        result = self.service.list_filters()
        self.assertEqual(result["filters"], [])
        self.assertTrue(result["stale"])
        self.assertEqual(result["error"], "Offline")

    def test_build_published_codes_and_generation_persist(self):
        build = self.service.load_build("https://maxroll.gg/d4/planner/nq4dbn0q")
        self.assertEqual(build["activeVariant"], 2)
        self.assertEqual(len(build["publishedFilters"]), 2)
        self.assertEqual(build["rejectedFilters"], 1)
        self.assertEqual(self.service.get_filter(build["publishedFilters"][0]["id"])["code"], PROFILE["data"]["lootFilters"][0]["code"])
        generated = self.service.generate_filter(build["id"], 1)
        self.assertEqual(generated["strictness"], "Highlight only")
        new_service = LootService(self.temp.name, self.client)
        self.assertEqual(new_service.get_filter(generated["id"])["code"], generated["code"])
        self.client.offline = True
        offline = new_service.load_build("https://maxroll.gg/d4/planner/nq4dbn0q")
        self.assertTrue(offline["stale"])
        self.assertTrue(new_service.generate_filter(build["id"], 1)["code"])

    def test_previously_loaded_guide_resolves_offline(self):
        url = "https://maxroll.gg/d4/build-guides/rain-of-arrows-rogue-guide"
        self.service.load_build(url)
        self.client.offline = True
        result = self.service.load_build(url)
        self.assertTrue(result["stale"])
        self.assertEqual(result["id"], "nq4dbn0q")

    def test_stale_mapping_diagnostic_and_strict_block(self):
        self.service.load_build("https://maxroll.gg/d4/planner/nq4dbn0q")
        self.service.store.write("game-mapping", {"mapping": MAPPING, "timestamp": time.time() - 100000})
        self.client.offline = True
        record = self.service.generate_filter("nq4dbn0q", 1)
        self.assertTrue(any("cached Maxroll" in note for note in record["diagnostics"]))
        with self.assertRaisesRegex(ValueError, "online"):
            self.service.generate_filter("nq4dbn0q", 1, True)

    def test_ids_cannot_escape_cache_directory(self):
        with self.assertRaises(ValueError):
            self.service.generate_filter("../secrets", 0)


if __name__ == "__main__":
    unittest.main()
