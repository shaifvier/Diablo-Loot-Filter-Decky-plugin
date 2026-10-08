"""Current Maxroll schema adapter around the pinned native filter encoder."""
from pathlib import Path

from .codec import decode_filter
from .vendor import d4_lootfilter as native

DATA = Path(__file__).parent / "vendor" / "data"
TYPE_KEYS = {
    "chest": "chest-armor", "2hbow": "bow", "2hcrossbow": "crossbow",
    "1hfocus": "focus", "1hshield": "shield", "1htotem": "totem",
    "2hsword": "two-handed-sword", "2haxe": "two-handed-axe",
    "2hmace": "two-handed-mace", "2hscythe": "two-handed-scythe",
    "2hstaff": "staff", "2hpolearm": "polearm", "2hglaive": "glaive",
    "2hquarterstaff": "quarterstaff", "1hsword": "sword", "1haxe": "axe",
    "1hmace": "mace", "1hdagger": "dagger", "1hwand": "wand",
    "1hscythe": "scythe", "1hflail": "flail", "1hcrossbow": "hand-crossbow",
}


class Generator:
    def __init__(self):
        self.affixes = native.AffixDB(DATA / "affixes.json")
        self.uniques = native.UniqueDB(DATA / "uniques.json")
        self.sets = native.TalismanSetDB(DATA / "talisman_sets.json")
        self.types = native.ItemTypeDB(DATA / "item_types.json")
        self.names = {}
        for db in (self.affixes, self.uniques, self.sets, self.types):
            self.names.update({key: value["name"] for key, value in db.by_hash.items()})

    def generate(self, build, variant_id, mapping, strict=False, name=None):
        data = build["data"]
        if not isinstance(variant_id, int) or isinstance(variant_id, bool) or not 0 <= variant_id < len(data["profiles"]):
            raise ValueError("Choose an existing build variant.")
        if not isinstance(strict, bool):
            raise ValueError("Strict mode must be true or false.")
        variant = data["profiles"][variant_id]
        name = (name or f"{build['name']} {variant.get('name', '')}").strip()[:30]
        if not name:
            raise ValueError("Give the filter a name.")
        groups, unique_ids, set_ids, missing = {}, [], [], []
        for slot, iid in (variant.get("items") or {}).items():
            item = data["items"].get(str(iid))
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                missing.append(f"Slot {slot}: item data unavailable")
                continue
            internal = item["id"]
            core = native._norm(internal)
            if core.startswith("talisman-seal"):
                continue
            if core.startswith("talisman-charm"):
                charm = native._charm_name(internal, self.uniques, self.sets)
                set_id = self.sets.match_charm(charm)
                if set_id is not None:
                    set_ids.append(set_id)
                    continue
                self._unique(charm, unique_ids, missing)
                continue
            # Runewords are fixed items, not legendary craft bases.
            if "unique" in core or core.startswith("runeword-"):
                self._unique(self.uniques.name_by_internal(internal) or core, unique_ids, missing)
                continue
            token = native._item_type(internal)
            key = TYPE_KEYS.get(token, token)
            type_id = self.types.type_id(key) if key else None
            if type_id is None:
                missing.append(f"Slot {slot}: unsupported item type {internal}")
                continue
            group = groups.setdefault(type_id, {"label": self.types.name(type_id), "slots": [],
                                               "keys": [key], "type_ids": [type_id],
                                               "ids": [], "ga": [], "names": {}})
            group["slots"].append(str(slot))
            # Tempered/implicit/aspect/transfiguration rows never enter this loop.
            for roll in item.get("explicits") or []:
                if not isinstance(roll, dict):
                    missing.append(f"{group['label']}: invalid affix data")
                    continue
                nid = roll.get("nid")
                sno = mapping.get(str(nid))
                if sno and any(part in native._norm(sno) for part in native.NON_AFFIX):
                    continue
                affix_key = self.affixes.key_by_sno(sno) if sno else None
                # Exact ID/name resolution only; never guess an affix by fuzzy matching.
                affix_id = self.affixes.key2hash.get(affix_key) if affix_key else None
                if affix_id is None and nid in self.affixes.by_hash:
                    affix_id = nid
                if affix_id is None:
                    missing.append(f"{group['label']}: {sno or 'unknown affix ' + str(nid)}")
                    continue
                if affix_id not in group["ids"]:
                    group["ids"].append(affix_id)
                    group["names"][affix_id] = self.affixes.name(affix_id)
                if roll.get("greater") and affix_id not in group["ga"]:
                    group["ga"].append(affix_id)
        missing = list(dict.fromkeys(missing))
        if strict and missing:
            raise ValueError("Strict generation requires complete mappings. Use Highlight mode or another variant. Missing: " + "; ".join(missing[:8]))
        rules = []
        for group in groups.values():
            if group["ids"]:
                group["n_bis"] = group["n_fix"] = min(native.NATURAL_AFFIXES, len(group["ids"]))
                rules.append(group)
        if not rules and not unique_ids and not set_ids:
            raise ValueError("No usable build gear was mapped. Try another variant.")
        code, count, dropped = native.build_filter_code(
            name, list(dict.fromkeys(unique_ids)), rules, hide_junk=strict,
            set_ids=list(dict.fromkeys(set_ids)),
            seal_type=self.types.type_id("horadric-seal"),
            charm_type=self.types.type_id("charm"),
            all_type_ids=[entry["_int"] for entry in self.types.entries])
        if count > 25:
            raise ValueError("This build needs more than 25 rules. Choose a simpler variant.")
        preview = decode_filter(code, self.names)
        diagnostics = missing + [f"Dropped BiS tier to fit 25 rules: {label}" for label in dropped]
        return code, preview, diagnostics

    def _unique(self, name, ids, missing):
        hashes = self.uniques.key2hashes.get(native._norm(name))
        if hashes:
            ids.extend(hashes)
        else:
            missing.append(f"Unique or runeword: {name} (kept visible)")
