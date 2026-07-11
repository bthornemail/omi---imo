#!/usr/bin/env python3
"""Run the small operational OMI-Lisp law subset used by ported OMI code."""

from __future__ import annotations

import argparse
from pathlib import Path


MASK8 = (1 << 8) - 1
MASK16 = (1 << 16) - 1
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == ";":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch in "()":
            tokens.append(ch)
            i += 1
            continue
        if ch == '"':
            i += 1
            value = ""
            while i < len(text):
                if text[i] == '"':
                    i += 1
                    break
                if text[i] == "\\" and i + 1 < len(text):
                    i += 1
                value += text[i]
                i += 1
            tokens.append(value)
            continue
        start = i
        while i < len(text) and not text[i].isspace() and text[i] not in "();":
            i += 1
        tokens.append(text[start:i])
    return tokens


def atom(token: str):
    if token == "true":
        return True
    if token == "false":
        return False
    if token.startswith("0x") or token.startswith("0X"):
        return int(token, 16)
    if token.startswith("-0x") or token.startswith("-0X"):
        return -int(token[1:], 16)
    try:
        return int(token, 10)
    except ValueError:
        return token


def parse_tokens(tokens: list[str]):
    index = 0

    def parse_expr():
        nonlocal index
        if index >= len(tokens):
            raise ValueError("unexpected eof")
        token = tokens[index]
        if token == "(":
            index += 1
            out = []
            while index < len(tokens) and tokens[index] != ")":
                out.append(parse_expr())
            if index >= len(tokens):
                raise ValueError("unclosed list")
            index += 1
            return out
        if token == ")":
            raise ValueError("unexpected close paren")
        index += 1
        return atom(token)

    forms = []
    while index < len(tokens):
        forms.append(parse_expr())
    return forms


class Module:
    def __init__(self, path: Path, source_text: str | None = None, name_hint: str | None = None):
        self.path = path
        self.source_text = source_text
        self.constants: dict[str, object] = {}
        self.functions: dict[str, tuple[list[str], object]] = {}
        self.tests: list[list[object]] = []
        self.name = name_hint or path.stem

    def load(self):
        source = self.source_text if self.source_text is not None else self.path.read_text(encoding="utf-8")
        forms = parse_tokens(tokenize(source))
        if len(forms) != 1 or not isinstance(forms[0], list) or forms[0][0] != "omi-module":
            raise ValueError(f"{self.path}: expected one omi-module form")
        module = forms[0]
        self.name = str(module[1])
        for form in module[2:]:
            if not isinstance(form, list) or not form:
                continue
            head = form[0]
            if head == "define-const":
                self.constants[str(form[1])] = self.eval_expr(form[2], {})
            elif head == "define-function":
                self.functions[str(form[1])] = ([str(p) for p in form[2]], form[3])
            elif head == "test":
                self.tests.append(form)

    def eval_expr(self, expr, env: dict[str, object]):
        if isinstance(expr, (int, bool)):
            return expr
        if isinstance(expr, str):
            if expr in env:
                return env[expr]
            if expr in self.constants:
                return self.constants[expr]
            raise ValueError(f"{self.path}: unknown symbol {expr}")
        if not isinstance(expr, list) or not expr:
            raise ValueError(f"{self.path}: invalid expression {expr!r}")

        op = str(expr[0])

        if op == "if":
            if len(expr) != 4:
                raise ValueError("if expects three args")
            return self.eval_expr(expr[2], env) if self.eval_expr(expr[1], env) else self.eval_expr(expr[3], env)
        if op in {"literal", "quote"}:
            if len(expr) != 2:
                raise ValueError(f"{op} expects one arg")
            return expr[1]
        if op == "and":
            for item in expr[1:]:
                if not self.eval_expr(item, env):
                    return False
            return True
        if op == "or":
            for item in expr[1:]:
                if self.eval_expr(item, env):
                    return True
            return False

        args = [self.eval_expr(arg, env) for arg in expr[1:]]

        if op == "u8":
            if len(args) != 1:
                raise ValueError("u8 expects one arg")
            return int(args[0]) & MASK8
        if op == "u16":
            if len(args) != 1:
                raise ValueError("u16 expects one arg")
            return int(args[0]) & MASK16
        if op == "u32":
            if len(args) != 1:
                raise ValueError("u32 expects one arg")
            return int(args[0]) & MASK32
        if op == "u64":
            if len(args) != 1:
                raise ValueError("u64 expects one arg")
            return int(args[0]) & MASK64
        if op == "bytes":
            return [int(arg) & MASK8 for arg in args]
        if op == "vector":
            return args
        if op in {"byte-at", "at"}:
            if len(args) != 2:
                raise ValueError(f"{op} expects two args")
            return args[0][int(args[1])]
        if op == "len":
            if len(args) != 1:
                raise ValueError("len expects one arg")
            return len(args[0])
        if op == "eq-bytes":
            if len(args) != 2:
                raise ValueError("eq-bytes expects two args")
            return list(args[0]) == list(args[1])
        if op == "receipt-string":
            if len(args) != 7:
                raise ValueError("receipt-string expects seven args")
            prefix = "V:" if args[0] else ""
            layers = ",".join(str(int(arg)) for arg in args[1:6])
            return f"{prefix}{layers};g{int(args[6])}"
        if op == "le32":
            if len(args) != 4:
                raise ValueError("le32 expects four args")
            return ((int(args[0]) & MASK8) |
                    ((int(args[1]) & MASK8) << 8) |
                    ((int(args[2]) & MASK8) << 16) |
                    ((int(args[3]) & MASK8) << 24)) & MASK32
        if op == "be64":
            if len(args) != 8:
                raise ValueError("be64 expects eight args")
            value = 0
            for arg in args:
                value = ((value << 8) | (int(arg) & MASK8)) & MASK64
            return value
        if op == "add":
            return sum(int(a) for a in args) & MASK64
        if op == "sub":
            if len(args) != 2:
                raise ValueError("sub expects two args")
            return (int(args[0]) - int(args[1])) & MASK64
        if op == "mul":
            value = 1
            for arg in args:
                value = (value * int(arg)) & MASK64
            return value
        if op == "mod":
            if len(args) != 2:
                raise ValueError("mod expects two args")
            return int(args[0]) % int(args[1])
        if op == "band":
            value = MASK64
            for arg in args:
                value &= int(arg)
            return value
        if op == "bor":
            value = 0
            for arg in args:
                value |= int(arg)
            return value & MASK64
        if op == "bxor":
            value = 0
            for arg in args:
                value ^= int(arg)
            return value & MASK64
        if op == "shl":
            if len(args) != 2:
                raise ValueError("shl expects two args")
            return (int(args[0]) << int(args[1])) & MASK64
        if op == "shr":
            if len(args) != 2:
                raise ValueError("shr expects two args")
            return (int(args[0]) >> int(args[1])) & MASK64
        if op == "eq":
            if len(args) != 2:
                raise ValueError("eq expects two args")
            return args[0] == args[1]
        if op == "ne":
            if len(args) != 2:
                raise ValueError("ne expects two args")
            return args[0] != args[1]
        if op in {"lt", "<"}:
            if len(args) != 2:
                raise ValueError("lt expects two args")
            return int(args[0]) < int(args[1])
        if op in {"le", "<="}:
            if len(args) != 2:
                raise ValueError("le expects two args")
            return int(args[0]) <= int(args[1])
        if op in {"gt", ">"}:
            if len(args) != 2:
                raise ValueError("gt expects two args")
            return int(args[0]) > int(args[1])
        if op in {"ge", ">="}:
            if len(args) != 2:
                raise ValueError("ge expects two args")
            return int(args[0]) >= int(args[1])
        if op == "not":
            if len(args) != 1:
                raise ValueError("not expects one arg")
            return not args[0]

        if op not in self.functions:
            raise ValueError(f"{self.path}: unknown function {op}")
        params, body = self.functions[op]
        if len(params) != len(args):
            raise ValueError(f"{op} expects {len(params)} args, got {len(args)}")
        call_env = dict(zip(params, args))
        return self.eval_expr(body, call_env)

    def run_tests(self) -> int:
        passed = 0
        for test in self.tests:
            name = str(test[1])
            for form in test[2:]:
                if not isinstance(form, list) or form[0] != "expect":
                    raise ValueError(f"{self.path}: unsupported test form in {name}")
                actual = self.eval_expr(form[1], {})
                expected = self.eval_expr(form[2], {})
                if actual != expected:
                    raise AssertionError(
                        f"{self.name}:{name}: expected {expected!r}, got {actual!r}"
                    )
                passed += 1
        return passed


def extract_org_omi_modules(path: Path) -> list[Module]:
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    modules: list[Module] = []
    current_lang = ""
    current_body: list[str] = []
    current_name = ""
    pending_name = ""

    for line in lines:
        if not current_lang:
            name_match = line.lower().startswith("#+name:")
            if name_match:
                pending_name = line.split(":", 1)[1].strip()
                continue
            lower = line.lower()
            if lower.startswith("#+begin_src "):
                parts = line.split()
                current_lang = parts[1].strip().lower() if len(parts) > 1 else ""
                current_name = pending_name
                pending_name = ""
                current_body = []
            continue

        if line.lower().strip() == "#+end_src":
            text = "\n".join(current_body).strip()
            if current_lang in {"omi", "omilisp", "omi-lisp"} and text.startswith("(omi-module"):
                hint = current_name or f"{path.stem}:{len(modules) + 1}"
                modules.append(Module(path, text, hint))
            current_lang = ""
            current_body = []
            current_name = ""
            continue

        current_body.append(line)

    return modules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args()

    total = 0
    for module_path in args.modules:
        path = Path(module_path)
        modules = extract_org_omi_modules(path) if path.suffix == ".org" else [Module(path)]
        if not modules:
            raise ValueError(f"{path}: no omi-module forms found")
        for module in modules:
            module.load()
            count = module.run_tests()
            total += count
            print(f"{module.name}: {count} checks passed")
    print(f"total: {total} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
