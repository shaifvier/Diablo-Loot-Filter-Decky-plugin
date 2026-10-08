"""Read-only Maxroll reference projection and independent local character progress."""
import hashlib
import json
import math
import re
import threading
import time
import uuid

from .providers import GAME_URL, utc_now
from .service import Store

GAME_TTL = 24 * 60 * 60
SLOTS = {4: "Helm", 5: "Chest", 6: "Main hand", 7: "Off hand", 8: "Dual wield", 9: "Two-handed weapon",
         10: "Ranged weapon", 11: "Weapon", 12: "Weapon", 13: "Gloves", 14: "Pants", 15: "Boots",
         16: "Ring 1", 17: "Ring 2", 18: "Amulet", 20: "Horadric Seal"}


def label(value):
    """Make internal identifiers readable without claiming an exact name mapping."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(value)).replace("_", " ")
    return text.strip()


def text(value):
    # Game descriptions contain a tooltip formula language. Never evaluate it.
    value = str(value or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    value = re.sub(r"\[[^\]]*\]", "…", value)
    value = re.sub(r"\{[^}]*\}", "", value)
    return value.strip()[:2000]


def index(value, length, message):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < length:
        raise ValueError(message)
    return value


def active(value, length):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < length else 0


def rotate(x, y, width, rotation):
    for _ in range(rotation):
        x, y = width - 1 - y, x
    return x, y


class Normalizer:
    def __init__(self, game, generator=None):
        self.game = game
        self.generator = generator
        self.diagnostics = []
        self.affixes = {str(v.get("id")): (k, v) for k, v in game.get("affixes", {}).items() if isinstance(v, dict)}

    def warn(self, message):
        if message not in self.diagnostics:
            self.diagnostics.append(message)

    def item(self, key):
        mapped = self.game.get("remap", {}).get("item", {}).get(key, {}).get("newId", key)
        return self.game.get("items", {}).get(mapped)

    def item_name(self, key):
        meta = self.item(key)
        if meta and meta.get("name"):
            return meta["name"]
        name = self.generator.uniques.name_by_internal(key) if self.generator else None
        if name:
            return name
        self.warn(f"Item name unavailable: {key}")
        return label(key) + " (identifier)"

    def affix(self, row):
        if not isinstance(row, dict):
            self.warn("An item has an unsupported affix record.")
            return {"name": "Unknown affix", "rolls": [], "greater": False, "description": ""}
        nid = row.get("nid")
        sno, meta = self.affixes.get(str(nid), (None, {}))
        name = self.generator.names.get(nid) if self.generator else None
        if not name and sno and self.generator:
            key = self.generator.affixes.key_by_sno(sno)
            name = self.generator.affixes.name(self.generator.affixes.key2hash[key]) if key else None
        if not name:
            name = meta.get("name") or (label(sno) if sno else f"Unknown affix ID {nid}")
        if not sno:
            self.warn(f"Affix mapping unavailable: {nid}")
        rolls = [v for v in row.get("values", []) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]
        return {"name": name, "rolls": rolls, "greater": bool(row.get("greater")), "description": text(meta.get("desc"))}

    def gear(self, build, variant):
        result = []
        for slot, iid in sorted((variant.get("items") or {}).items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 999):
            item = build["data"]["items"].get(str(iid))
            if not isinstance(item, dict):
                self.warn(f"Equipment slot {slot} has no item data.")
                continue
            key = str(item.get("id") or "Unknown item")
            number = int(slot) if str(slot).isdigit() else -1
            slot_name = SLOTS.get(number, f"Charm {number - 20}" if 21 <= number <= 28 else f"Slot {slot}")
            sockets = []
            for socket in item.get("sockets") or []:
                sid = socket if isinstance(socket, str) else str(socket.get("id", "Unknown socket")) if isinstance(socket, dict) else str(socket)
                meta = self.item(sid) or self.game.get("stones", {}).get(sid) or {}
                sockets.append(meta.get("name") or label(sid))
            result.append({"slot": slot_name, "id": key, "name": item.get("name") or self.item_name(key),
                           "power": item.get("power"), "mythic": bool(item.get("mythic")),
                           "natural": [self.affix(r) for r in item.get("explicits") or []],
                           "implicit": [self.affix(r) for r in item.get("implicits") or []],
                           "tempered": [self.affix(r) for r in item.get("tempered") or []],
                           "aspects": [self.affix(r) for r in item.get("aspects") or []], "sockets": sockets})
        return result

    def skill_name(self, key):
        meta = self.game.get("skills", {}).get(key, {})
        if not meta:
            self.warn(f"Skill name unavailable: {key}")
        return meta.get("name") or label(key)

    def skills(self, variant):
        cls = self.game.get("classes", {}).get(str(variant.get("class")), {})
        tree = self.game.get("skillTrees", {}).get(cls.get("tree"), {})
        source = variant.get("skillTree") or {}
        steps = source.get("steps") or []
        result = []
        if not tree:
            self.warn("Skill tree geometry is unavailable; use the allocation list.")
        for si, step in enumerate(steps):
            allocations = step.get("data") or {}
            nodes, ids = [], set()
            for source_node in tree.get("nodes", [])[:3000]:
                nid = str(source_node.get("id"))
                reward = self.game.get("skillTreeRewards", {}).get(source_node.get("rewardId"), {})
                power = self.game.get("skills", {}).get(reward.get("power"), {})
                upgrade = next((m for m in power.get("mods", []) if m.get("id") == reward.get("mod")), {})
                name = upgrade.get("name") or power.get("name") or ("Unknown skill " + nid if source_node.get("rewardId") else "Junction")
                if source_node.get("rewardId") and not power:
                    self.warn(f"Skill node mapping unavailable: {nid}")
                rank = allocations.get(nid, 0)
                rank = rank if isinstance(rank, int) and not isinstance(rank, bool) and 0 <= rank <= 100 else 0
                pos = source_node.get("pos") or {}
                x, y = pos.get("x"), pos.get("y")
                if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
                    self.warn(f"Skill node position unavailable: {nid}")
                    continue
                ids.add(nid)
                nodes.append({"id": nid, "name": name, "x": x / 100, "y": y / 100,
                              "rank": rank, "maxRank": reward.get("ranks", 0), "allocated": rank > 0,
                              "selectable": bool(source_node.get("rewardId")), "description": text(upgrade.get("desc") or power.get("desc")),
                              "kind": "Upgrade" if reward.get("type") == 1 else "Passive" if reward.get("type") == 2 else "Skill"})
            entries = [dict(n) for n in nodes if n["allocated"]]
            for nid, rank in allocations.items():
                if nid not in ids and isinstance(rank, int) and not isinstance(rank, bool) and rank > 0:
                    self.warn(f"Allocated skill node missing from diagram: {nid}")
                    entries.append({"id": nid, "name": "Unknown skill node " + nid, "rank": rank,
                                    "maxRank": None, "kind": "Unknown", "description": ""})
            connections = []
            for edge in tree.get("connections", [])[:5000]:
                a, b = str(edge.get("node1")), str(edge.get("node2"))
                if a in ids and b in ids:
                    corners = [{"x": p["x"] / 100, "y": p["y"] / 100} for p in edge.get("corners", [])
                               if isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k]) for k in ("x", "y"))]
                    connections.append({"from": a, "to": b, "corners": corners})
            result.append({"id": si, "name": step.get("name") or f"Step {si + 1}", "nodes": nodes,
                           "connections": connections, "allocations": entries})
        bar = [{"id": key, "name": self.skill_name(key)} for key in variant.get("skillBar", [])[:8] if isinstance(key, str)]
        mechanics = []
        if cls.get("minionPowers"):
            for i, family in enumerate(cls["minionPowers"]):
                choices = family.get("types", [])
                specs = variant.get("minionSpec", [])
                upgrades = variant.get("minionUpgrades", [])
                choice = choices[specs[i]] if i < len(specs) and isinstance(specs[i], int) and 0 <= specs[i] < len(choices) else {}
                upgrade = self.skill_name(upgrades[i]) if i < len(upgrades) and upgrades[i] else ""
                mechanics.append(f"{family.get('name', 'Minion')}: {choice.get('name', 'Unknown')} {upgrade}".strip())
        elif variant.get("specialization") is not None:
            mechanics.append("Specialization: " + self.skill_name(str(variant["specialization"])))
        return {"steps": result, "activeStep": active(source.get("position"), len(result)), "bar": bar, "mechanics": mechanics}

    def paragon(self, variant):
        source = variant.get("paragon") or {}
        result = []
        for si, step in enumerate(source.get("steps") or []):
            boards, occurrences = [], {}
            for bi, board in enumerate(step.get("data") or []):
                bid = str(board.get("id") or "Unknown board")
                occurrence = occurrences.get(bid, 0)
                occurrences[bid] = occurrence + 1
                uid = f"{bid}:{occurrence}"
                meta = self.game.get("paragonBoards", {}).get(bid, {})
                width, grid = meta.get("width"), meta.get("nodes", [])
                rotation = board.get("rotation", 0)
                if not isinstance(rotation, int) or isinstance(rotation, bool) or rotation not in range(4):
                    self.warn(f"Board rotation unavailable: {bid}")
                    rotation = 0
                valid = isinstance(width, int) and not isinstance(width, bool) and 1 <= width <= 40 and isinstance(grid, list) and len(grid) == width * width
                if not valid:
                    self.warn(f"Board geometry unavailable: {bid}; use the allocation list.")
                    width, grid = 0, []
                selected = {str(k) for k, v in (board.get("nodes") or {}).items() if isinstance(v, (int, float)) and v > 0}
                nodes, connections = [], []
                for ni, key in enumerate(grid):
                    if not key:
                        continue
                    nm = self.game.get("paragonNodes", {}).get(key, {})
                    if not nm:
                        self.warn(f"Paragon node name unavailable: {key}")
                    x, y = rotate(ni % width, ni // width, width, rotation)
                    generic = re.fullmatch(r"Generic_(?:Normal|Magic)_(.+)", str(key))
                    suffix = generic[1] if generic else None
                    common_name = {"Str": "Strength", "Dex": "Dexterity", "Int": "Intelligence", "Will": "Willpower"}.get(suffix)
                    name = nm.get("name") or ((common_name or label(suffix)) if generic and nm else label(key) + " (identifier)")
                    stats = []
                    for attr in nm.get("attributes", []):
                        am = self.game.get("attributes", {}).get(str(attr.get("id")), {})
                        stats.append(label(am.get("name") or f"Attribute {attr.get('id')}").removesuffix(" Core"))
                    nodes.append({"id": str(ni), "key": f"{uid}/{ni}", "name": name,
                                  "x": x * 24, "y": y * 24, "allocated": str(ni) in selected,
                                  "rarity": nm.get("rarity", 0), "gate": bool(nm.get("gate")),
                                  "socket": "socket" in str(key).lower(), "description": ", ".join(stats)})
                    for neighbor in (ni + 1 if ni % width < width - 1 else -1, ni + width):
                        if 0 <= neighbor < len(grid) and grid[neighbor]:
                            connections.append({"from": str(ni), "to": str(neighbor), "corners": []})
                entries = [dict(n) for n in nodes if n["allocated"]]
                ids = {n["id"] for n in nodes}
                for nid in sorted(selected - ids):
                    self.warn(f"Allocated paragon node missing from diagram: {bid}/{nid}")
                    entries.append({"id": nid, "key": f"{uid}/{nid}", "name": "Unknown node " + nid, "allocated": True, "description": ""})
                glyph_id = board.get("glyph")
                glyph = self.game.get("paragonGlyphs", {}).get(glyph_id, {})
                if glyph_id and not glyph:
                    self.warn(f"Glyph name unavailable: {glyph_id}")
                boards.append({"id": uid, "sourceId": bid, "name": meta.get("name") or label(bid), "order": bi + 1,
                               "width": width, "rotation": rotation, "position": board.get("position"),
                               "nodes": nodes, "connections": connections, "allocations": entries,
                               "glyph": {"id": glyph_id, "name": glyph.get("name") or label(glyph_id or "No glyph"), "level": board.get("glyphLevel")}})
            result.append({"id": si, "name": step.get("name") or f"Step {si + 1}", "boards": boards})
        return {"steps": result, "activeStep": active(source.get("position"), len(result))}

    def reference(self, build, variant_id):
        variants = build["data"]["profiles"]
        variant = variants[index(variant_id, len(variants), "Choose an existing build variant.")]
        gear, skills, paragon = self.gear(build, variant), self.skills(variant), self.paragon(variant)
        return {"id": build["id"], "name": build["name"], "className": build["cls"].title(),
                "season": f"S{build['season']}" if isinstance(build.get("season"), int) else "Unknown",
                "sourceUrl": build.get("url"), "updatedAt": build.get("updatedAt"), "fetchedAt": build.get("fetchedAt"),
                "variantId": variant_id, "variantName": variant.get("name") or f"Variant {variant_id + 1}",
                "variants": [{"id": i, "name": v.get("name") or f"Variant {i + 1}"} for i, v in enumerate(variants)],
                "gameVersion": self.game.get("version"), "gear": gear, "skills": skills, "paragon": paragon,
                "diagnostics": self.diagnostics, "stale": False, "error": None}


class ViewerService:
    def __init__(self, loot_service, path):
        self.loot = loot_service
        self.store = Store(path)
        self.lock = threading.RLock()
        self._game_memory = None
        self._retry_at = 0
        self._references = {}

    def list_builds(self):
        result = []
        for p in self.loot.store.path.glob("build-*.json"):
            bid = p.stem[6:]
            if not re.fullmatch(r"[A-Za-z0-9]{4,32}", bid):
                continue
            b = self.loot.store.read(p.stem)
            if b and isinstance(b.get("data", {}).get("profiles"), list):
                result.append({"id": bid, "name": b.get("name", "Maxroll build"), "className": str(b.get("cls", "Unknown")).title(),
                               "season": self.loot._season(b), "fetchedAt": b.get("fetchedAt"),
                               "activeVariant": active(b["data"].get("activeProfile"), len(b["data"]["profiles"]))})
        return sorted(result, key=lambda b: b.get("fetchedAt") or "", reverse=True)

    def _game(self):
        cached = self._game_memory or self.store.read("game-data")
        if cached and time.time() - cached.get("timestamp", 0) < GAME_TTL:
            self._game_memory = cached
            return cached["game"], None
        if cached and time.time() < self._retry_at:
            return cached["game"], "Using cached viewer game data; the provider is unavailable."
        try:
            game = self.loot.client.json(GAME_URL)
            if not isinstance(game.get("skillTrees"), dict) or not isinstance(game.get("paragonBoards"), dict):
                raise ValueError("Maxroll's viewer data format changed.")
            cached = {"game": game, "timestamp": time.time()}
            self.store.write("game-data", cached)
            self._game_memory = cached
            return game, None
        except (ValueError, OSError) as exc:
            if cached:
                self._game_memory = cached
                self._retry_at = time.time() + 60
                return cached["game"], "Using cached viewer game data. " + str(exc)
            raise

    def get_reference(self, build_id, variant_id):
        if not isinstance(build_id, str) or not re.fullmatch(r"[A-Za-z0-9]{4,32}", build_id):
            raise ValueError("Choose a saved Maxroll build.")
        with self.lock:
            path = self.loot.store.path / f"build-{build_id}.json"
            stamp = path.stat().st_mtime_ns if path.is_file() else None
            build = self.loot.store.read("build-" + build_id)
            if not build:
                raise ValueError("Load this Maxroll build first.")
            index(variant_id, len(build["data"]["profiles"]), "Choose an existing build variant.")
            build = dict(build, id=build_id)
            try:
                game, warning = self._game()
                key = (build_id, variant_id, stamp, self._game_memory["timestamp"])
                ref = self._references.get(key)
                if ref is None:
                    ref = Normalizer(game, self.loot.generator).reference(build, variant_id)
                    if len(self._references) >= 16:
                        self._references.clear()
                    self._references[key] = ref
                    self.store.write(f"reference-{build_id}-{variant_id}", ref)
                ref = dict(ref)
                ref.update(stale=bool(warning), error=warning)
                return ref
            except (ValueError, OSError) as exc:
                ref = self.store.read(f"reference-{build_id}-{variant_id}")
                if ref:
                    return dict(ref, stale=True, error=str(exc))
                raise

    def list_characters(self):
        with self.lock:
            return list(self.store.read("characters", {}).values())

    def save_character(self, character_id, name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
            raise ValueError("Use a character name between 1 and 40 characters.")
        with self.lock:
            chars = self.store.read("characters", {})
            if character_id is not None and character_id not in chars:
                raise ValueError("Choose an existing character.")
            cid = character_id or str(uuid.uuid4())
            chars[cid] = {"id": cid, "name": name.strip()}
            self.store.write("characters", chars)
            return chars[cid]

    def delete_character(self, character_id):
        with self.lock:
            chars = self.store.read("characters", {})
            if character_id not in chars:
                raise ValueError("Choose an existing character.")
            del chars[character_id]
            progress = self.store.read("progress", {})
            progress = {k: v for k, v in progress.items() if not k.startswith(character_id + ":")}
            self.store.write("progress", progress)
            self.store.write("characters", chars)
            return True

    def _scope(self, character_id, build_id, variant_id, step_id):
        if not isinstance(character_id, str) or character_id not in self.store.read("characters", {}):
            raise ValueError("Choose a character for the checklist.")
        ref = self.get_reference(build_id, variant_id)
        steps = ref["paragon"]["steps"]
        step = steps[index(step_id, len(steps), "Choose an existing paragon step.")]
        keys = {n["key"] for b in step["boards"] for n in b["allocations"]}
        snapshot = [(b["id"], b["rotation"], b["glyph"], sorted(n["key"] for n in b["allocations"])) for b in step["boards"]]
        fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        return f"{character_id}:{build_id}:{variant_id}:{step_id}", keys, fingerprint

    def get_progress(self, character_id, build_id, variant_id, step_id):
        with self.lock:
            scope, keys, fingerprint = self._scope(character_id, build_id, variant_id, step_id)
            all_progress = self.store.read("progress", {})
            old = all_progress.get(scope, {})
            completed = sorted(set(old.get("completed", [])) & keys)
            changed = bool(old.get("fingerprint") and old["fingerprint"] != fingerprint)
            state = {"completed": completed, "fingerprint": fingerprint, "needsReview": bool(old.get("needsReview")) or changed,
                     "total": len(keys)}
            if state != old:
                all_progress[scope] = state
                self.store.write("progress", all_progress)
            return state

    def set_progress(self, character_id, build_id, variant_id, step_id, completed):
        if not isinstance(completed, list) or len(completed) > 10000 or not all(isinstance(k, str) for k in completed):
            raise ValueError("Invalid paragon checklist.")
        with self.lock:
            scope, keys, fingerprint = self._scope(character_id, build_id, variant_id, step_id)
            if not set(completed) <= keys:
                raise ValueError("Only nodes allocated by this build can be marked completed. Reload the build.")
            state = {"completed": sorted(set(completed)), "fingerprint": fingerprint, "needsReview": False,
                     "total": len(keys)}
            all_progress = self.store.read("progress", {})
            all_progress[scope] = state
            self.store.write("progress", all_progress)
            return state


def seed_preview(cache, stable_cache):
    """Copy public build/filter caches once; never modify or share the stable store."""
    cache = Store(cache)
    if cache.read("preview-seeded"):
        return
    copied = []
    if stable_cache.is_dir():
        for p in stable_cache.glob("*.json"):
            if p.name not in {"catalog.json", "saved.json", "guide-links.json", "game-mapping.json"} and not re.fullmatch(r"build-[A-Za-z0-9]{4,32}\.json", p.name):
                continue
            if not (cache.path / p.name).exists():
                try:
                    value = json.loads(p.read_text())
                    cache.write(p.stem, value)
                    copied.append(p.name)
                except (OSError, ValueError):
                    continue
    cache.write("preview-seeded", {"copied": copied, "at": utc_now()})
