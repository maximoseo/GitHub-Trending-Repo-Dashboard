# -*- coding: utf-8 -*-
"""Shared categorization, scoring, and merge helpers for GitHub Awesome trending data."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

CATEGORIES = {
    "agents": {
        "label": "Agents / OpenClaw / Hermes",
        "keywords": [
            "agent",
            "openclaw",
            "hermes",
            "claw",
            "copaw",
            "clawhub",
            "clawpal",
            "zeroclaw",
            "molt",
            "openclaw",
        ],
    },
    "claude": {
        "label": "Claude Code",
        "keywords": [
            "claude",
            "anthropic",
            "holyclaude",
            "codex",
        ],
    },
    "skills_mcp": {
        "label": "Skills & MCP",
        "keywords": ["skill", "mcp", "context", "prompt"],
    },
    "seo_marketing": {
        "label": "SEO & Marketing",
        "keywords": [
            "seo",
            "marketing",
            "content",
            "geo",
            "aso",
            "analytics",
            "schema",
            "sitemap",
        ],
    },
    "frontend_design": {
        "label": "Frontend & Design",
        "keywords": [
            "frontend",
            "design",
            "html",
            "css",
            "tailwind",
            "react",
            "vue",
            "ui",
            "ux",
            "figma",
            "slide",
            "markdown-site",
        ],
    },
    "browser_automation": {
        "label": "Browser & Automation",
        "keywords": [
            "browser",
            "playwright",
            "puppeteer",
            "crawl",
            "scraper",
            "scraping",
            "8xbrowser",
            "automation",
        ],
    },
    "coding_devtools": {
        "label": "Coding & Dev tools",
        "keywords": [
            "code",
            "dev",
            "cursor",
            "sdk",
            "cli",
            "git",
            "terminal",
            "tui",
            "vscode",
        ],
    },
}

EXCLUDE_KEYWORDS = [
    "tts",
    "text-to-speech",
    "robotics",
    "game",
    "minecraft",
    "music-gen",
    "stable-diffusion",
    "comfyui",
    "onnx",
    "trading-bot",
    "crypto",
]

GITHUB_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.I,
)


def normalize_github_url(url: str) -> str | None:
    m = GITHUB_RE.search(url.strip())
    if not m:
        return None
    owner = m.group("owner").lower()
    repo = m.group("repo").lower().removesuffix(".git")
    return f"https://github.com/{owner}/{repo}"


def parse_owner_repo(url: str) -> tuple[str, str]:
    path = urlparse(url).path.strip("/").split("/")
    if len(path) >= 2:
        return path[0].lower(), path[1].lower()
    return "", ""


def parse_md_table(md_text: str) -> list[tuple[str, str]]:
    """Parse the summary table in examples markdown: | name | url |."""
    rows: list[tuple[str, str]] = []
    in_table = False
    for line in md_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table and rows:
                break
            continue
        if "---" in stripped:
            in_table = True
            continue
        if not in_table:
            continue
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if not url.startswith("http"):
            continue
        norm = normalize_github_url(url)
        if norm:
            rows.append((name, norm))
    return rows


def episodes_payload_window(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return episode dicts from bootstrap JSON payload."""
    eps = payload.get("episodes_in_window") or payload.get("episodes") or []
    return sorted(eps, key=lambda e: int(e.get("episode", 0)))


def score_repo(name: str, owner: str, url: str) -> int:
    blob = f"{name} {owner} {url}".lower()
    if any(ex in blob for ex in EXCLUDE_KEYWORDS):
        return 0
    score = 0
    for cat in CATEGORIES.values():
        for kw in cat["keywords"]:
            if kw in blob:
                score += 1
    if score >= 2:
        score += 1
    return score


def categorize_repo(name: str, owner: str, url: str) -> list[str]:
    blob = f"{name} {owner} {url}".lower()
    if score_repo(name, owner, url) < 2:
        return []
    tags: list[str] = []
    for cat_id, cat in CATEGORIES.items():
        if any(kw in blob for kw in cat["keywords"]):
            tags.append(cat_id)
    return tags


def merge_repos(
    existing: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    for url, row in incoming.items():
        key = url.lower().rstrip("/")
        if key not in existing:
            existing[key] = row
            continue
        cur = existing[key]
        cur["categories"] = sorted(
            set(cur.get("categories", [])) | set(row.get("categories", []))
        )
        cur["episodes"] = sorted(
            set(cur.get("episodes", [])) | set(row.get("episodes", []))
        )
        cur["score"] = max(int(cur.get("score", 0)), int(row.get("score", 0)))
        cur["first_seen"] = min(cur.get("first_seen", "9999"), row.get("first_seen", "9999"))
        cur["last_seen"] = max(cur.get("last_seen", ""), row.get("last_seen", ""))
        seen = {(s.get("type"), s.get("video_id")) for s in cur.get("sources", [])}
        for src in row.get("sources", []):
            sig = (src.get("type"), src.get("video_id"))
            if sig not in seen:
                cur.setdefault("sources", []).append(src)
                seen.add(sig)
    return existing


def episodes_from_titles(repo_name: str, episodes: list[dict]) -> list[int]:
    """Match repo slug to episode titles (token + hyphenated slug in title)."""
    slug = repo_name.lower()
    tokens = {t for t in re.split(r"[^a-z0-9]+", slug) if len(t) >= 3}
    matched: list[int] = []
    for ep in episodes:
        title = (ep.get("title") or "").lower()
        if slug in title:
            matched.append(int(ep["episode"]))
            continue
        if tokens and tokens.issubset(
            {t for t in re.split(r"[^a-z0-9]+", title) if len(t) >= 3}
        ):
            matched.append(int(ep["episode"]))
    return sorted(set(matched))


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
