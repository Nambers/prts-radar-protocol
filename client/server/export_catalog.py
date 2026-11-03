#!/usr/bin/env python3
"""导出纯前端版内置的命令目录：python3 client/server/export_catalog.py [--check]"""
from __future__ import annotations

import json
import pathlib
import sys

import protocol as P

OUT = pathlib.Path(__file__).resolve().parents[1] / "web" / "src" / "catalog.json"


def build() -> dict:
    base = P.catalog_json()
    by_name = {c["name"]: c for c in base["commands"]}
    by_fw = {}
    for ver in base["fw"]["known"]:
        cat = P.catalog_json(ver)
        assert [c["name"] for c in cat["commands"]] == list(by_name), ver
        delta = {}
        for c in cat["commands"]:
            b = by_name[c["name"]]
            d = {k: c.get(k) for k in sorted(c.keys() | b.keys()) if c.get(k) != b.get(k)}
            if d:
                delta[c["name"]] = d
        fw = {k: v for k, v in cat["fw"].items() if k != "known"}
        by_fw[ver] = {"fw": fw, "commands": delta}
    return {"base": base, "byFw": by_fw}


def main() -> int:
    text = json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"
    if "--check" in sys.argv[1:]:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT} 已过期 —— 重跑 export_catalog.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT} ({len(text.encode()) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
