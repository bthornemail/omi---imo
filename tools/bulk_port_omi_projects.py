#!/usr/bin/env python3
"""Bulk-convert sibling OMI projects into OMI-Lisp declaration inventories."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECTS = [
    "o---o",
    "omi-axioms",
    "omi-canon",
    "omi-canvas",
    "omi-docs",
    "omi-isa",
    "omi-lisp",
    "omi-media",
    "omi-port",
    "omi-portal",
    "omi-protocol",
    "omi-tetragrammatron",
    "omi-vault",
    "omnicron",
]


def symbol(value: str) -> str:
    return value.lower().replace("_", "-")


def run_project(repo_root: Path, omi_root: Path, name: str) -> dict[str, object] | None:
    source = omi_root / name
    if not source.is_dir():
        print(f"skip missing {source}")
        return None

    port_name = f"{symbol(name)}-port"
    output = repo_root / "declarations" / port_name
    cmd = [
        sys.executable,
        str(repo_root / "tools" / "port_omnicron_to_omilisp.py"),
        "--source-root",
        str(source),
        "--output-root",
        str(output),
        "--project-prefix",
        port_name,
        "--title-prefix",
        f"{name} port: ",
        "--declaration-kind",
        f"{symbol(name)}.source-candidate",
        "--graph-scope",
        symbol(name),
        "--locator",
        f"omi---imo.{port_name}",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)
    manifest = json.loads((output / "MANIFEST.json").read_text(encoding="ascii"))
    return {
        "project": name,
        "port": port_name,
        "source_root": str(source),
        "output_root": str(output),
        "count": manifest["count"],
        "family_counts": manifest["family_counts"],
        "extension_counts": manifest["extension_counts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--omi-root", default="/home/main/omi")
    parser.add_argument("--repo-root", default="/home/main/omi/omi---imo")
    parser.add_argument("projects", nargs="*", default=PROJECTS)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    omi_root = Path(args.omi_root).resolve()
    results = []
    for name in args.projects:
        result = run_project(repo_root, omi_root, name)
        if result is not None:
            results.append(result)

    total = sum(int(item["count"]) for item in results)
    aggregate = {
        "omi_root": str(omi_root),
        "repo_root": str(repo_root),
        "project_count": len(results),
        "declaration_count": total,
        "projects": results,
    }
    aggregate_path = repo_root / "declarations" / "OMI_PROJECT_PORTS.json"
    aggregate_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"wrote {aggregate_path}")
    print(f"total projects: {len(results)}")
    print(f"total declarations: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
