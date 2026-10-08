#!/usr/bin/env python3
"""Build the clipboard helper and create an allowlisted Decky installation ZIP."""
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    if not (ROOT / "dist/index.js").is_file():
        raise SystemExit("Build the frontend first: pnpm build")
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    binary = output / "d4-clipboard"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(ROOT / "backend/src/clipboard.c"), "-o", str(binary), "-lX11"], check=True)
    version = json.loads((ROOT / "package.json").read_text())["version"]
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    artifact = artifact_dir / f"diablo-loot-filters-v{version}.zip"
    files = [(ROOT / p, p) for p in ("main.py", "plugin.json", "package.json", "README.md", "VALIDATION.md", "LICENSE", "LICENSE.template", "THIRD_PARTY_NOTICES.md", "dist/index.js")]
    files.extend((p, str(p.relative_to(ROOT))) for p in (ROOT / "backend").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
    files.append((binary, "bin/d4-clipboard"))
    with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as bundle:
        for source, path in sorted(files, key=lambda pair: pair[1]):
            bundle.write(source, "diablo-loot-filters/" + path)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(".zip.sha256").write_text(f"{digest}  {artifact.name}\n")
    print(f"Created {artifact} ({artifact.stat().st_size:,} bytes)")
    return artifact


if __name__ == "__main__":
    package()
