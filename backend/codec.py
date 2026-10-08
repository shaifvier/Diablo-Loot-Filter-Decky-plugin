"""Bounded protobuf reader for native D4 share codes; no generated runtime needed."""
import base64
import binascii
import struct

MAX_CODE_LENGTH = 128_000


def fields(data):
    def varint(pos):
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError("Truncated filter code.")
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value, pos
        raise ValueError("Invalid filter integer.")

    pos = 0
    while pos < len(data):
        tag, pos = varint(pos)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid filter field.")
        if wire == 0:
            value, pos = varint(pos)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, pos = varint(pos)
            else:
                size = 8 if wire == 1 else 4
            if pos + size > len(data):
                raise ValueError("Truncated filter field.")
            value = data[pos:pos + size]
            pos += size
            if wire == 5:
                value = struct.unpack("<I", value)[0]
        else:
            raise ValueError("Unsupported filter wire type.")
        yield number, wire, value


def decode_filter(code, names=None):
    if not isinstance(code, str) or len(code) > MAX_CODE_LENGTH:
        raise ValueError("Filter code is too large or missing.")
    code = "".join(code.split())
    try:
        raw = base64.b64decode(code, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("This is not a valid Diablo IV import code.") from exc
    names = names or {}
    result = {"name": "Unnamed filter", "rules": []}
    for number, wire, value in fields(raw):
        if number == 2 and wire == 2:
            result["name"] = value.decode("utf-8")
        elif number == 1 and wire == 2:
            rule = {"name": "Rule", "action": "Show", "enabled": True,
                    "color": None, "conditions": []}
            for rn, rw, rv in fields(value):
                if rn == 1 and rw == 2:
                    rule["name"] = rv.decode("utf-8")
                elif rn == 2 and rw == 0:
                    rule["action"] = {0: "Show", 1: "Hide label", 2: "Highlight", 3: "Hide"}.get(rv, f"Action {rv}")
                elif rn == 3 and rw == 5:
                    rule["color"] = f"#{rv & 0xffffff:06x}"
                elif rn == 5 and rw == 0:
                    rule["enabled"] = bool(rv)
                elif rn == 4 and rw == 2:
                    rule["conditions"].append(condition_text(rv, names))
            result["rules"].append(rule)
    if not 1 <= len(result["rules"]) <= 25:
        raise ValueError("A Diablo IV filter must contain 1–25 rules.")
    result["ruleCount"] = len(result["rules"])
    return result


def condition_text(data, names):
    values = {}
    ids, greater = [], []
    for n, w, v in fields(data):
        if n == 2 and w == 5:
            ids.append(v)
        elif n == 2 and w == 2 and len(v) % 4 == 0:
            ids.extend(struct.unpack("<" + "I" * (len(v) // 4), v))
        elif n == 3 and w == 2:
            greater.extend(pv for pn, pw, pv in fields(v) if pn == 1 and pw == 5)
        elif w == 0:
            values[n] = v
    kind = values.get(1, 0)
    labels = [names.get(i, f"ID {i}") for i in ids]
    if kind == 1:
        rarities = [(1, "Common"), (2, "Magic"), (4, "Rare"), (8, "Legendary"),
                    (16, "Unique"), (32, "Mythic"), (64, "Set charm")]
        return "Rarity: " + ", ".join(label for bit, label in rarities if values.get(4, 0) & bit)
    if kind == 2:
        return "Item properties: Ancestral" if values.get(4, 0) & 4 else f"Item properties: {values.get(4, 0)}"
    if kind == 3:
        return "Codex of Power upgrade"
    if kind == 4:
        return f"Greater Affixes: at least {values.get(4, 0)}"
    if kind in (5, 6, 7, 8, 9):
        label = {5: "Item types", 6: "Required affixes", 7: "Optional affixes", 8: "Uniques", 9: "Charm sets"}[kind]
        text = label + ": " + ", ".join(labels)
        if kind in (6, 7):
            text += f" (at least {values.get(4, 0)})"
        if greater:
            text += "; Greater: " + ", ".join(names.get(i, f"ID {i}") for i in greater)
        return text
    return f"Condition {kind}; values {values.get(4, 0)}, {values.get(5, 0)}, {values.get(6, 0)}"
