# -*- coding: utf-8 -*-
"""
Extract repos from @GithubAwesome Trending Today videos.

Modes:
  --mode full        Backfill all episodes in window (requires yt-dlp)
  --mode incremental Only new video IDs not in sync_state

Requires: pip install requests beautifulsoup4 yt-dlp (for full/incremental crawl)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from githubawesome_lib import (
    categorize_repo,
    iso_now,
    merge_repos,
    normalize_github_url,
    parse_owner_repo,
    score_repo,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / ".cache" / "githubawesome"
ENRICHED = DATA / "githubawesome-trending-repos-enriched.json"

GITHUB_URL_RE = re.compile(r"https?://github\.com/[^\s\)>\"']+", re.I)
EPISODE_RE = re.compile(r"GitHub Trending Today #(\d+)", re.I)


def load_enriched() -> dict:
    if ENRICHED.exists():
        return json.loads(ENRICHED.read_text(encoding="utf-8"))
    return {
        "generated_at": iso_now(),
        "cutoff": "2025-11-26",
        "sync_state": {
            "last_sync_at": None,
            "last_sync_status": "idle",
            "last_sync_run_id": None,
            "processed_video_ids": [],
            "last_episode_number": 0,
        },
        "episodes": [],
        "repos": [],
    }


def save_enriched(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    ENRICHED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def extract_urls_from_text(text: str) -> list[str]:
    urls = []
    for raw in GITHUB_URL_RE.findall(text or ""):
        norm = normalize_github_url(raw)
        if norm:
            urls.append(norm)
    return sorted(set(urls))


def repo_row(url: str, episode: int, video_id: str, upload_date: str) -> dict | None:
    owner, name = parse_owner_repo(url)
    score = score_repo(name, owner, url)
    if score < 2:
        return None
    cats = categorize_repo(name, owner, url)
    if not cats:
        return None
    return {
        "name": name,
        "url": url,
        "owner": owner,
        "categories": cats,
        "score": score,
        "episodes": [episode],
        "first_seen": upload_date,
        "last_seen": upload_date,
        "sources": [{"type": "extract", "episode": episode, "video_id": video_id}],
    }


def run_incremental() -> int:
    print("Incremental mode: install yt-dlp and implement channel listing for production crawl.")
    print("Use bootstrap_from_examples.py for initial data until crawl is wired.")
    data = load_enriched()
    data["sync_state"]["last_sync_status"] = "idle"
    data["generated_at"] = iso_now()
    save_enriched(data)
    return 0


def run_full(months: int) -> int:
    print(f"Full mode ({months} months): requires yt-dlp — run in GitHub Actions with network access.")
    return run_incremental()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()

    if args.mode == "full":
        return run_full(args.months)
    return run_incremental()


if __name__ == "__main__":
    raise SystemExit(main())
