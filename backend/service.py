"""Persistent catalogue, build and generated-filter service."""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .codec import decode_filter
from .generator import Generator
from .providers import HTTPClient, GAME_URL, PROFILE_URL, load_catalog, normalize_profile, resolve_planner, utc_now

CATALOG_TTL = 6 * 60 * 60
GAME_TTL = 24 * 60 * 60


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def read(self, key, default=None):
        try:
            return json.loads((self.path / (key + ".json")).read_text())
        except (OSError, ValueError):
            return default

    def write(self, key, value):
        target = self.path / (key + ".json")
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False))
        os.replace(temporary, target)


class LootService:
    def __init__(self, cache_dir, client=None):
        self.store = Store(cache_dir)
        self.client = client or HTTPClient()
        self.generator = Generator()
        self.lock = threading.RLock()

    def list_filters(self, refresh=False):
        with self.lock:
            cached = self.store.read("catalog")
            error = None
            if refresh or not cached or time.time() - cached.get("timestamp", 0) >= CATALOG_TTL:
                try:
                    records = load_catalog(self.client)
                    filters = []
                    rejected = 0
                    for record in records:
                        if not record.get("importCode"):
                            continue
                        try:
                            filters.append(self._catalog_record(record))
                        except (ValueError, UnicodeError):
                            rejected += 1
                    if not filters:
                        raise ValueError("The catalogue contains no structurally valid import codes.")
                    cached = {"timestamp": time.time(), "fetchedAt": utc_now(), "filters": filters,
                              "rejected": rejected}
                    self.store.write("catalog", cached)
                except (ValueError, OSError) as exc:
                    error = str(exc)
            saved = self.store.read("saved", {})
            records = list(saved.values()) + ((cached or {}).get("filters") or [])
            return {"filters": [self._summary(r) for r in records],
                    "fetchedAt": (cached or {}).get("fetchedAt"),
                    "stale": bool(error) or not cached,
                    "error": error, "rejected": (cached or {}).get("rejected", 0)}

    def _catalog_record(self, record):
        code = record["importCode"]
        preview = decode_filter(code, self.generator.names)
        return {"id": "catalog:" + record["id"], "title": record.get("title") or preview["name"],
                "className": record.get("className") or "Unknown", "buildName": record.get("buildName") or "General",
                "stage": record.get("stage") or "Unknown", "strictness": record.get("strictness") or "Unknown",
                "season": record.get("season") or "Unknown", "updatedAt": record.get("lastCheckedAt"),
                "sourceName": record.get("sourceName") or "Community",
                "sourceUrl": record.get("sourceUrl") or "https://diablo4lootfilter.com/filters/" + record["slug"],
                "catalogUrl": "https://diablo4lootfilter.com/filters/" + record["slug"],
                "creator": record.get("creatorName") or "Unknown",
                "verification": "Source reports in-game tested" if record.get("inGameVerification") == "in_game_verified" else "Not in-game verified",
                "origin": "Published", "code": code, "preview": preview, "diagnostics": []}

    @staticmethod
    def _summary(record):
        return {k: v for k, v in record.items() if k not in ("code", "preview", "diagnostics")}

    def get_filter(self, filter_id):
        if not isinstance(filter_id, str):
            raise ValueError("Select a filter first.")
        with self.lock:
            saved = self.store.read("saved", {})
            if filter_id in saved:
                return saved[filter_id]
            cached = self.store.read("catalog", {})
            for record in cached.get("filters", []):
                if record["id"] == filter_id:
                    return record
        raise ValueError("This filter is no longer cached. Refresh the catalogue.")

    def load_build(self, url):
        with self.lock:
            url = url.strip()
            guides = self.store.read("guide-links", {})
            try:
                planner_id = resolve_planner(self.client, url)
                guides[url] = planner_id
                self.store.write("guide-links", guides)
            except ValueError:
                planner_id = guides.get(url)
                if not planner_id:
                    raise
            stale, error = False, None
            try:
                profile = self.client.json(PROFILE_URL.format(planner_id))
                build = normalize_profile(profile)
                build.update({"id": planner_id, "url": url.strip(), "fetchedAt": utc_now()})
                self.store.write("build-" + planner_id, build)
            except (ValueError, OSError) as exc:
                build = self.store.read("build-" + planner_id)
                if not build:
                    raise
                stale, error = True, str(exc)
            embedded = []
            rejected = 0
            saved = self.store.read("saved", {})
            for index, item in enumerate(build["data"].get("lootFilters") or []):
                if not isinstance(item, dict) or not item.get("code"):
                    continue
                try:
                    preview = decode_filter(item["code"], self.generator.names)
                except (ValueError, UnicodeError):
                    rejected += 1
                    continue
                fid = f"maxroll:{planner_id}:{index}"
                record = self._build_record(build, fid, item.get("name") or "Published filter", "Published", item["code"], preview, [])
                saved[fid] = record
                embedded.append(self._summary(record))
            self.store.write("saved", saved)
            active = build["data"].get("activeProfile", 0)
            if not isinstance(active, int) or not 0 <= active < len(build["data"]["profiles"]):
                active = 0
            return {"id": planner_id, "name": build["name"], "className": build["cls"].title(),
                    "season": self._season(build), "updatedAt": build["updatedAt"], "fetchedAt": build["fetchedAt"],
                    "variants": [{"id": i, "name": v.get("name") or f"Variant {i + 1}"} for i, v in enumerate(build["data"]["profiles"])],
                    "activeVariant": active, "publishedFilters": embedded, "rejectedFilters": rejected,
                    "stale": stale, "error": error}

    def _mapping(self):
        cached = self.store.read("game-mapping")
        if cached and time.time() - cached.get("timestamp", 0) < GAME_TTL:
            return cached["mapping"], None
        try:
            game = self.client.json(GAME_URL)
            mapping = {str(value["id"]): key for key, value in game.get("affixes", {}).items() if isinstance(value, dict) and "id" in value}
            if not mapping:
                raise ValueError("Maxroll affix data is unavailable.")
            self.store.write("game-mapping", {"mapping": mapping, "timestamp": time.time(), "version": game.get("version")})
            return mapping, None
        except (ValueError, OSError):
            if cached:
                return cached["mapping"], "Using cached Maxroll affix data; refresh when online."
            raise

    def generate_filter(self, build_id, variant_id, strict=False, name=None):
        if not isinstance(build_id, str) or not build_id.isalnum() or len(build_id) > 32:
            raise ValueError("Load a Maxroll build first.")
        with self.lock:
            build = self.store.read("build-" + build_id)
            if not build:
                raise ValueError("Load this Maxroll build again.")
            mapping, warning = self._mapping()
            if strict and warning:
                raise ValueError("Refresh Maxroll affix data online before generating a strict filter.")
            code, preview, diagnostics = self.generator.generate(build, variant_id, mapping, strict, name)
            if warning:
                diagnostics.append(warning)
            digest = hashlib.sha256(code.encode()).hexdigest()[:16]
            record = self._build_record(build, "generated:" + digest,
                                       build["data"]["profiles"][variant_id].get("name") or "Generated filter",
                                       "Generated", code, preview, diagnostics)
            record["strictness"] = "Strict" if strict else "Highlight only"
            record["updatedAt"] = utc_now()
            saved = self.store.read("saved", {})
            saved[record["id"]] = record
            self.store.write("saved", saved)
            return record

    @staticmethod
    def _season(build):
        value = build.get("season")
        return f"S{value}" if isinstance(value, int) and value > 0 else "Unknown"

    def _build_record(self, build, fid, title, origin, code, preview, diagnostics):
        return {"id": fid, "title": f"{build['name']} · {title}", "className": build["cls"].title() or "Unknown",
                "buildName": build["name"], "stage": title if origin == "Generated" else "Build guide",
                "strictness": title if origin == "Published" else "Highlight only", "season": self._season(build),
                "updatedAt": build.get("updatedAt"), "sourceName": "Maxroll", "sourceUrl": build["url"],
                "creator": "Maxroll build author", "verification": "Not in-game verified", "origin": origin,
                "code": code, "preview": preview, "diagnostics": diagnostics}
