# -*- coding: utf-8 -*-
"""Export enriched JSON to categorized Markdown."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from githubawesome_lib import CATEGORIES

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SRC = DATA_DIR / "githubawesome-trending-repos-enriched.json"
OUT = DATA_DIR / "githubawesome-trending-repos.md"


def main() -> int:
    if not SRC.exists():
        print(f"Missing {SRC}", file=sys.stderr)
        return 1

    data = json.loads(SRC.read_text(encoding="utf-8"))
    repos = data.get("repos", [])

    lines = [
        "# GitHub Awesome — Trending Repos for Hermes / OpenClaw / Claude Code",
        "",
        "Source channel: https://www.youtube.com/@GithubAwesome",
        f"Generated: {data.get('generated_at', '')}",
        f"Cutoff: {data.get('cutoff', '')}",
        f"Total repos: **{len(repos)}**",
        "",
        "| Repository | GitHub URL |",
        "| --- | --- |",
    ]

    for r in sorted(repos, key=lambda x: x.get("name", "").lower()):
        lines.append(f"| {r['name']} | {r['url']} |")

    lines.extend(["", "## Summary by category", ""])
    by_cat: dict[str, list] = defaultdict(list)
    for r in repos:
        for c in r.get("categories", []):
            by_cat[c].append(r)

    lines.append("| Category | Count |")
    lines.append("| --- | --- |")
    for cat_id, cat in CATEGORIES.items():
        lines.append(f"| {cat['label']} | {len(by_cat.get(cat_id, []))} |")

    for cat_id, cat in CATEGORIES.items():
        rows = by_cat.get(cat_id, [])
        if not rows:
            continue
        lines.extend(["", f"## {cat['label']}", "", "| Repository | GitHub URL | Episodes |", "| --- | --- | --- |"])
        for r in sorted(rows, key=lambda x: (-x.get("score", 0), x.get("name", ""))):
            eps = ", ".join(f"#{e}" for e in r.get("episodes", [])) or "—"
            lines.append(f"| {r['name']} | {r['url']} | {eps} |")

    lines.extend([
        "",
        "## All repositories (alphabetical)",
        "",
        "| Repository | GitHub URL | Categories | Score |",
        "| --- | --- | --- | --- |",
    ])
    for r in sorted(repos, key=lambda x: x.get("name", "").lower()):
        cats = ", ".join(r.get("categories", []))
        lines.append(f"| {r['name']} | {r['url']} | {cats} | {r.get('score', 0)} |")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
