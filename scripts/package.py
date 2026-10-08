#!/usr/bin/env python3
"""Build the clipboard helper and create an allowlisted Decky installation ZIP."""
import hashlib
import argparse
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package(preview=False):
    frontend = ROOT / ("dist-preview" if preview else "dist") / "index.js"
    if not frontend.is_file():
        raise SystemExit("Build the frontend first: pnpm build")
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    binary = output / "d4-clipboard"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(ROOT / "backend/src/clipboard.c"), "-o", str(binary), "-lX11"], check=True)
    version = json.loads((ROOT / "package.json").read_text())["version"]
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    slug = "diablo-loot-filters-preview" if preview else "diablo-loot-filters"
    artifact = artifact_dir / f"{slug}-v{version}.zip"
    files = [(ROOT / p, p) for p in ("main.py", "package.json", "README.md", "VALIDATION.md", "LICENSE", "LICENSE.template", "THIRD_PARTY_NOTICES.md")]
    files.extend([(ROOT / ("preview/plugin.json" if preview else "plugin.json"), "plugin.json"), (frontend, "dist/index.js")])
    expected_name = "Diablo Loot Filters Preview" if preview else "Diablo Loot Filters"
    if f'const manifest = {{"name":"{expected_name}"}};' not in frontend.read_text():
        raise SystemExit("Frontend/plugin identity mismatch. Rebuild the matching frontend.")
    files.extend((p, str(p.relative_to(ROOT))) for p in (ROOT / "backend").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
    files.append((binary, "bin/d4-clipboard"))
    with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as bundle:
        for source, path in sorted(files, key=lambda pair: pair[1]):
            bundle.write(source, slug + "/" + path)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(".zip.sha256").write_text(f"{digest}  {artifact.name}\n")
    print(f"Created {artifact} ({artifact.stat().st_size:,} bytes)")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    package(parser.parse_args().preview)
