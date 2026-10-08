"""Integration test: run under xvfb-run with xclip available (CI)."""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.clipboard import Clipboard
from backend.codec import decode_filter
from backend.providers import parse_catalog_chunk

root = Path(__file__).resolve().parents[1]
code = parse_catalog_chunk((root / "tests/fixtures/catalog-chunk.js").read_text())[0]["importCode"]
owner = Clipboard(root / "out/d4-clipboard")
try:
    result = owner.copy(code)
    assert result["copied"], result
    # No frontend exists here; owner must continue serving after the copy call returns.
    time.sleep(0.25)
    for target in ["UTF8_STRING", "STRING"]:
        pasted = subprocess.check_output(["xclip", "-selection", "clipboard", "-out", "-target", target], timeout=5).decode()
        assert pasted == code, (target, len(pasted), len(code))
        decode_filter(pasted)
    assert owner.copy(code)["copied"], "A second copy must replace and reap the previous owner"
    print("Clipboard persistence and UTF8/STRING round trips passed on", os.environ.get("DISPLAY"))
finally:
    owner.close()
assert not owner.processes
