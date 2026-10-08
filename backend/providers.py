"""Public provider adapters. Downloaded scripts are parsed as data, never executed."""
import gzip
import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin

CATALOG_URL = "https://diablo4lootfilter.com/filters"
PROFILE_URL = "https://planners.maxroll.gg/profiles/load/d4/{}"
GAME_URL = "https://assets-ng.maxroll.gg/d4-tools/game/data.min.json"
ALLOWED_HOSTS = {"diablo4lootfilter.com", "www.diablo4lootfilter.com", "maxroll.gg",
                 "www.maxroll.gg", "planners.maxroll.gg", "assets-ng.maxroll.gg"}
MAX_RESPONSE = 24 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_url(url, hosts=ALLOWED_HOSTS):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Enter a supported HTTPS URL.")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Only HTTPS links to supported providers are accepted.")
    return parsed


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTPClient:
    def __init__(self):
        # Decky's frozen Python does not reliably discover host CA certificates.
        # Use the distro's trust store while retaining full TLS verification.
        bundle = next((p for p in (Path("/etc/ssl/cert.pem"), Path("/etc/ssl/certs/ca-certificates.crt"),
                                  Path("/etc/pki/tls/certs/ca-bundle.crt")) if p.is_file()), None)
        context = ssl.create_default_context(cafile=str(bundle) if bundle else None)
        self.opener = urllib.request.build_opener(SafeRedirect(), urllib.request.HTTPSHandler(context=context))

    def text(self, url):
        validate_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "text/html,application/json,*/*"})
        try:
            with self.opener.open(request, timeout=25) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ValueError("Provider response is too large.")
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                    if len(raw) > MAX_RESPONSE:
                        raise ValueError("Provider response is too large.")
                return raw.decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Provider returned HTTP {exc.code}. Try again later.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logging.getLogger("DiabloLootFilters").warning("Provider transport: %s: %s", type(exc).__name__, str(exc))
            raise ValueError("Could not reach the provider. Check your connection and retry.") from exc

    def json(self, url):
        return json.loads(self.text(url))


def script_links(html):
    # Decky's embedded Python omits html.parser. We only need quoted src
    # attributes on script tags; accept same-origin Next static bundle paths.
    return [src for _, src in re.findall(r'<script\b[^>]*\ssrc\s*=\s*(["\'])(.*?)\1', html, re.I | re.S)
            if src.startswith("/_next/static/") and src.endswith(".js")]


class LiteralParser:
    """Restricted JS object literal grammar. Rejects calls, expressions and code."""
    def __init__(self, text, pos=0):
        self.text, self.pos = text, pos

    def space(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def value(self, depth=0):
        if depth > 20:
            raise ValueError("Catalogue data is too deeply nested.")
        self.space()
        ch = self.text[self.pos:self.pos + 1]
        if ch in ('"', "'") and ch:
            return self.string()
        if ch == "{":
            self.pos += 1
            result = {}
            self.space()
            while self.text[self.pos:self.pos + 1] != "}":
                self.space()
                if self.text[self.pos:self.pos + 1] in ('"', "'"):
                    key = self.string()
                else:
                    match = re.match(r"[A-Za-z_$][\w$]*", self.text[self.pos:])
                    if not match:
                        raise ValueError("Invalid catalogue property.")
                    key = match[0]
                    self.pos += len(key)
                self.expect(":")
                result[key] = self.value(depth + 1)
                self.space()
                if self.text[self.pos:self.pos + 1] != ",":
                    break
                self.pos += 1
            self.expect("}")
            return result
        if ch == "[":
            self.pos += 1
            result = []
            self.space()
            while self.text[self.pos:self.pos + 1] != "]":
                result.append(self.value(depth + 1))
                self.space()
                if self.text[self.pos:self.pos + 1] != ",":
                    break
                self.pos += 1
            self.expect("]")
            return result
        for token, value in [("true", True), ("false", False), ("null", None), ("!0", True), ("!1", False)]:
            if self.text.startswith(token, self.pos):
                self.pos += len(token)
                return value
        match = re.match(r"-?\d+(?:\.\d+)?", self.text[self.pos:])
        if match:
            self.pos += len(match[0])
            return json.loads(match[0])
        raise ValueError("Catalogue contains an unsupported expression.")

    def expect(self, char):
        self.space()
        if self.text[self.pos:self.pos + 1] != char:
            raise ValueError("Invalid catalogue data.")
        self.pos += 1

    def string(self):
        quote = self.text[self.pos]
        self.pos += 1
        result = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(result)
            if char == "\\":
                char = self.text[self.pos]
                self.pos += 1
                if char in ("u", "x"):
                    size = 4 if char == "u" else 2
                    result.append(chr(int(self.text[self.pos:self.pos + size], 16)))
                    self.pos += size
                else:
                    result.append(escapes.get(char, char))
            else:
                result.append(char)
        raise ValueError("Unclosed catalogue string.")


def parse_catalog_chunk(text):
    records = []
    for match in re.finditer(r'\{id\s*:\s*["\']', text):
        try:
            value = LiteralParser(text, match.start()).value()
        except (ValueError, IndexError):
            continue
        if isinstance(value, dict) and value.get("game") == "Diablo IV" and value.get("slug"):
            records.append(value)
    return list({record["id"]: record for record in records}.values())


def load_catalog(client):
    html = client.text(CATALOG_URL)
    # Discover content-addressed bundle names on every refresh; never hardcode hashes.
    for path in dict.fromkeys(script_links(html)):
        text = client.text(urljoin(CATALOG_URL, path))
        if "importCode:" not in text:
            continue
        records = parse_catalog_chunk(text)
        if records:
            return records
    raise ValueError("The catalogue format changed. Cached filters are still available.")


def resolve_planner(client, url):
    parsed = validate_url(url, {"maxroll.gg", "www.maxroll.gg"})
    match = re.fullmatch(r"/d4/planner/([A-Za-z0-9]{4,32})/?", parsed.path)
    if match and match[1] != "builds":
        return match[1]
    if not re.fullmatch(r"/d4/build-guides/[a-z0-9-]+/?", parsed.path):
        raise ValueError("Use a Maxroll Diablo IV build-guide or planner link.")
    html = client.text(url)
    ids = [v for v in re.findall(r"(?:https?:)?(?://)?(?:www\.)?maxroll\.gg/d4/planner/([A-Za-z0-9]+)", html) if v != "builds"]
    if not ids:
        raise ValueError("No planner was found in this guide. Paste its D4 planner link instead.")
    return ids[0]


def normalize_profile(profile):
    data = profile.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list) or not isinstance(data.get("items"), dict):
        raise ValueError("Maxroll returned an unsupported planner format.")
    variants = data["profiles"]
    if not variants or not all(isinstance(v, dict) for v in variants):
        raise ValueError("This planner has no usable build variants.")
    return {"name": profile.get("name") or "Maxroll build",
            "cls": str(profile.get("class") or "").lower(), "data": data,
            "updatedAt": profile.get("date"), "season": data.get("season")}
