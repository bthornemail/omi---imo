#!/usr/bin/env python3
"""Generate OMI-Lisp declaration candidates for project source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


TEXT_EXTENSIONS = {
    "",
    ".S",
    ".c",
    ".cc",
    ".gyp",
    ".h",
    ".html",
    ".js",
    ".json",
    ".ld",
    ".lisp",
    ".logic",
    ".lx",
    ".md",
    ".mjs",
    ".ndjson",
    ".omi",
    ".org",
    ".pl",
    ".py",
    ".rs",
    ".scm",
    ".sha256",
    ".sh",
    ".toml",
    ".tst",
    ".txt",
    ".yml",
    ".svg",
    ".bitboard",
}

SKIP_SUFFIXES = {
    ".pyc",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}

CODE_EXTENSIONS = {
    ".S",
    ".c",
    ".cc",
    ".h",
    ".js",
    ".mjs",
    ".py",
    ".rs",
    ".sh",
}

DECLARATION_EXTENSIONS = {
    ".json",
    ".ndjson",
    ".logic",
    ".lx",
    ".omi",
    ".org",
    ".pl",
    ".scm",
    ".lisp",
    ".bitboard",
}

DOC_EXTENSIONS = {
    ".md",
    ".txt",
}

CARRIER_EXTENSIONS = {
    ".bin",
    ".flat",
    ".flat2",
    ".gif",
    ".pdf",
    ".pgm",
    ".png",
    ".PNG",
    ".svg",
}


def sexpr_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def symbol(value: str) -> str:
    out = value.lower()
    out = re.sub(r"[^a-z0-9]+", "-", out)
    out = out.strip("-")
    return out or "root"


def file_extension(path: Path) -> str:
    return path.suffix if path.suffix else "[no-ext]"


def file_family(ext: str) -> str:
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in DECLARATION_EXTENSIONS:
        return "declaration"
    if ext in DOC_EXTENSIONS:
        return "document"
    if ext in CARRIER_EXTENSIONS:
        return "carrier"
    if ext == "[no-ext]":
        return "untyped"
    return "artifact"


def read_text(path: Path) -> str | None:
    ext = path.suffix
    if ext not in TEXT_EXTENSIONS and ext != "":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except UnicodeDecodeError:
            return None


def balanced_parens(text: str) -> bool:
    depth = 0
    in_string = False
    escape = False
    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_string


def text_metrics(path: Path, text: str) -> list[tuple[str, str | int]]:
    ext = path.suffix
    lines = text.splitlines()
    metrics: list[tuple[str, str | int]] = [
        ("line-count", len(lines)),
    ]

    if ext in {".c", ".h", ".cc"}:
        funcs = re.findall(
            r"^\s*(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w\s\*]*\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{",
            text,
            re.MULTILINE,
        )
        defines = re.findall(r"^\s*#\s*define\s+([A-Za-z_]\w*)", text, re.MULTILINE)
        includes = re.findall(r"^\s*#\s*include\s+[<\"]([^>\"]+)[>\"]", text, re.MULTILINE)
        metrics.extend(
            [
                ("function-count", len(funcs)),
                ("define-count", len(defines)),
                ("include-count", len(includes)),
            ]
        )
    elif ext in {".js", ".mjs"}:
        exports = re.findall(r"\bexport\s+(?:function|const|class|default)\b", text)
        funcs = re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", text)
        metrics.extend(
            [
                ("function-count", len(funcs)),
                ("export-count", len(exports)),
            ]
        )
    elif ext == ".json":
        try:
            parsed = json.loads(text)
            kind = "array" if isinstance(parsed, list) else "object" if isinstance(parsed, dict) else type(parsed).__name__
            metrics.extend(
                [
                    ("json-valid", "true"),
                    ("json-kind", kind),
                ]
            )
            if isinstance(parsed, dict):
                metrics.append(("json-key-count", len(parsed)))
            elif isinstance(parsed, list):
                metrics.append(("json-item-count", len(parsed)))
        except json.JSONDecodeError:
            metrics.append(("json-valid", "false"))
    elif ext == ".ndjson":
        records = 0
        valid = True
        for line in lines:
            if not line.strip():
                continue
            try:
                json.loads(line)
                records += 1
            except json.JSONDecodeError:
                valid = False
        metrics.extend(
            [
                ("ndjson-valid", "true" if valid else "false"),
                ("record-count", records),
            ]
        )
    elif ext in {".md", ".org"}:
        title = ""
        for line in lines:
            stripped = line.strip()
            if ext == ".md" and stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                break
            if ext == ".org" and stripped.startswith("*"):
                title = stripped.lstrip("*").strip()
                break
        if title:
            metrics.append(("title", title[:160]))
    elif ext in {".lisp", ".scm", ".logic", ".pl", ".omi"}:
        metrics.append(("balanced-parens", "true" if balanced_parens(text) else "false"))
    elif ext == ".svg":
        metrics.append(("svg-root", "true" if "<svg" in text[:512].lower() else "false"))

    return metrics


def declaration_for(
    source_root: Path,
    path: Path,
    project_prefix: str,
    title_prefix: str,
    declaration_kind: str,
    graph_scope: str,
    locator: str,
) -> tuple[str, dict[str, str | int]]:
    rel = path.relative_to(source_root).as_posix()
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    ext = file_extension(path)
    family = file_family(ext)
    sid = f"{project_prefix}.{symbol(rel)}"
    out_name = f"{symbol(rel)}.omilisp"
    text = read_text(path)
    metrics = text_metrics(path, text) if text is not None else []
    if text is None:
        metrics.append(("text-readable", "false"))
    else:
        metrics.append(("text-readable", "true"))

    lines = [
        "(omi",
        "  (identity",
        f"    (sid {sid})",
        f"    (title {sexpr_string(title_prefix + rel)})",
        f"    (kind {declaration_kind})",
        f"    (source {sexpr_string(str(source_root / rel))})",
        "    (reference \"/home/main/omi/omi-lisp/SPEC.md\")",
        "    (reference \"/home/main/omi/omi-lisp/LOWERING.md\")",
        "    (reference \"/home/main/omi/omi-isa/README.md\"))",
        "  (address",
        f"    (addr {sid})",
        f"    (locator {locator})",
        f"    (binding {symbol(ext)}.source-carrier.v0))",
        "  (scope",
        "    (fs omi)",
        f"    (gs {graph_scope})",
        f"    (rs {family})",
        f"    (us {symbol(ext)}))",
        "  (source-artifact",
        f"    (relative-path {sexpr_string(rel)})",
        f"    (extension {sexpr_string(ext)})",
        f"    (family {family})",
        f"    (bytes {len(data)})",
        f"    (sha256 {sexpr_string(digest)}))",
        "  (authority",
        "    (declaration candidate)",
        "    (accepted-state false)",
        "    (validation downstream)",
        "    (receipt pending)",
        "    (carrier-authority false))",
        "  (omi-lisp-boundary",
        "    (pre-header unary-control)",
        "    (sp-boundary required-before-dot)",
        "    (lowering-target typed-construction-candidate))",
        "  (conversion",
        "    (method metadata-and-typed-source-summary)",
        "    (source-content-copied false)",
        "    (runtime-state-copied false)",
        "    (receipt-created false))",
        "  (metrics",
    ]
    for key, value in metrics:
        if isinstance(value, int):
            lines.append(f"    ({key} {value})")
        elif value in {"true", "false"}:
            lines.append(f"    ({key} {value})")
        else:
            lines.append(f"    ({key} {sexpr_string(value)})")
    lines.extend(
        [
            "    (metric-version 1))",
            "  (projections",
            "    (lazy source-reference)",
            "    (greedy typed-summary)",
            "    (static manifest)",
            "    (animated none))",
            "  (receipts",
            "    (identity pending)",
            "    (projection pending)))",
            "",
        ]
    )

    manifest = {
        "sid": sid,
        "relative_path": rel,
        "output": out_name,
        "extension": ext,
        "family": family,
        "bytes": len(data),
        "sha256": digest,
    }
    return "\n".join(lines), manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="/home/main/omi/omnicron")
    parser.add_argument("--output-root", default="/home/main/omi/omi---imo/declarations/omnicron-port")
    parser.add_argument("--project-prefix", default="omnicron-port")
    parser.add_argument("--title-prefix", default="Omnicron port: ")
    parser.add_argument("--declaration-kind", default="omnicron.source-candidate")
    parser.add_argument("--graph-scope", default="omnicron")
    parser.add_argument("--locator", default="omi---imo.omnicron-port")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    for old in output_root.glob("*.omilisp"):
        old.unlink()

    manifests = []
    for path in sorted(source_root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        declaration, manifest = declaration_for(
            source_root,
            path,
            args.project_prefix,
            args.title_prefix,
            args.declaration_kind,
            args.graph_scope,
            args.locator,
        )
        (output_root / manifest["output"]).write_text(declaration, encoding="ascii")
        manifests.append(manifest)

    counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for item in manifests:
        counts[str(item["extension"])] = counts.get(str(item["extension"]), 0) + 1
        family_counts[str(item["family"])] = family_counts.get(str(item["family"]), 0) + 1

    manifest_doc = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "count": len(manifests),
        "extension_counts": dict(sorted(counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "items": manifests,
    }
    (output_root / "MANIFEST.json").write_text(
        json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )

    print(f"generated {len(manifests)} omilisp declarations in {output_root}")
    for family, count in sorted(family_counts.items()):
        print(f"{family}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
