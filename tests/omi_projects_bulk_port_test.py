#!/usr/bin/env python3
"""Verify aggregate OMI project bulk-port manifests."""

from __future__ import annotations

import json
from pathlib import Path


EXPECTED_COUNTS = {
    "o---o": 355,
    "omi-axioms": 172,
    "omi-canon": 412,
    "omi-canvas": 329,
    "omi-docs": 87,
    "omi-isa": 125,
    "omi-lisp": 118,
    "omi-media": 231,
    "omi-port": 45,
    "omi-portal": 968,
    "omi-protocol": 29,
    "omi-tetragrammatron": 173,
    "omi-vault": 508,
    "omnicron": 439,
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    aggregate_path = root / "declarations" / "OMI_PROJECT_PORTS.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="ascii"))
    projects = {item["project"]: item for item in aggregate["projects"]}

    assert aggregate["project_count"] == len(EXPECTED_COUNTS)
    assert set(projects) == set(EXPECTED_COUNTS)
    assert aggregate["declaration_count"] == sum(EXPECTED_COUNTS.values())

    for project, expected_count in EXPECTED_COUNTS.items():
        item = projects[project]
        assert item["count"] == expected_count, project
        manifest_path = root / "declarations" / item["port"] / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        assert manifest["count"] == expected_count, project
        assert len(manifest["items"]) == expected_count, project
        assert sum(manifest["family_counts"].values()) == expected_count, project

    print("ALL OMI PROJECT BULK PORT MANIFESTS VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
