#!/usr/bin/env python3
"""Project runnable canon OMI-Lisp law modules to a JSON Canvas surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from omilisp_law_runner import Module, extract_org_omi_modules


DEFAULT_MODULES = [
    "declarations/canon-operational/envelope-bitboard.omilisp",
    "declarations/canon-operational/orbit.omilisp",
    "declarations/canon-operational/sense-pg.omilisp",
    "declarations/canon-operational/omicron-receipt.omilisp",
    "declarations/canon-operational/omiom.omilisp",
    "declarations/canon-operational/semantic-lattice.omilisp",
]


def stable_id(*parts: object) -> str:
    text = "\0".join(str(part) for part in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def load_modules(paths: list[Path]) -> list[Module]:
    modules: list[Module] = []
    for path in paths:
        found = extract_org_omi_modules(path) if path.suffix == ".org" else [Module(path)]
        if not found:
            raise ValueError(f"{path}: no omi-module forms found")
        for module in found:
            module.load()
            modules.append(module)
    return modules


def module_color(index: int) -> str:
    return str((index % 6) + 1)


def project_modules(paths: list[Path]) -> dict[str, list[dict[str, str]]]:
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []

    root_id = "canon-operational-runtime"
    nodes.append({
        "id": root_id,
        "type": "text",
        "text": "canon operational runtime projection; executable candidate; no state acceptance",
        "color": "1",
    })

    modules = load_modules(paths)
    for index, module in enumerate(modules):
        check_count = module.run_tests()
        module_id = "module-" + stable_id(module.path, module.name)
        nodes.append({
            "id": module_id,
            "type": "text",
            "text": f"{module.name}: {check_count} checks passed; projection only",
            "color": module_color(index),
        })
        edges.append({
            "fromNode": root_id,
            "toNode": module_id,
            "fromSide": "right",
            "toSide": "left",
            "toEnd": "arrow",
            "label": "contains",
        })

        for test in module.tests:
            test_name = str(test[1])
            test_id = "test-" + stable_id(module.path, module.name, test_name)
            expect_count = sum(1 for form in test[2:] if isinstance(form, list) and form and form[0] == "expect")
            nodes.append({
                "id": test_id,
                "type": "text",
                "text": f"{test_name}: {expect_count} expectation(s)",
                "color": module_color(index),
            })
            edges.append({
                "fromNode": module_id,
                "toNode": test_id,
                "fromSide": "right",
                "toSide": "left",
                "toEnd": "arrow",
                "label": "witnesses",
            })

    return {"nodes": nodes, "edges": edges}


def validate_canvas(canvas: dict[str, list[dict[str, str]]]) -> None:
    node_ids = set()
    for node in canvas.get("nodes", []):
        if set(node) != {"id", "type", "text", "color"}:
            raise AssertionError(f"invalid node keys: {sorted(node)}")
        if node["type"] != "text":
            raise AssertionError(f"unsupported node type: {node['type']}")
        if node["id"] in node_ids:
            raise AssertionError(f"duplicate node id: {node['id']}")
        node_ids.add(node["id"])

    if not node_ids:
        raise AssertionError("projection produced no nodes")

    for edge in canvas.get("edges", []):
        if set(edge) != {"fromNode", "toNode", "fromSide", "toSide", "toEnd", "label"}:
            raise AssertionError(f"invalid edge keys: {sorted(edge)}")
        if edge["fromNode"] not in node_ids:
            raise AssertionError(f"edge source missing node: {edge['fromNode']}")
        if edge["toNode"] not in node_ids:
            raise AssertionError(f"edge target missing node: {edge['toNode']}")
        if edge["toEnd"] != "arrow":
            raise AssertionError(f"unsupported edge ending: {edge['toEnd']}")


def canonical_json(canvas: dict[str, list[dict[str, str]]]) -> str:
    return json.dumps(canvas, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("modules", nargs="*", default=DEFAULT_MODULES)
    args = parser.parse_args()

    paths = [Path(module) for module in args.modules]
    canvas = project_modules(paths)
    validate_canvas(canvas)

    if args.verify:
        second = project_modules(paths)
        if canonical_json(canvas) != canonical_json(second):
            raise AssertionError("projection is not deterministic")
        print(
            f"canon operational canvas projection: "
            f"{len(canvas['nodes'])} nodes, {len(canvas['edges'])} edges"
        )
        return 0

    print(canonical_json(canvas), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
