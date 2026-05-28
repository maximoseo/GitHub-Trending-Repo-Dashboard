# -*- coding: utf-8 -*-
"""Bootstrap enriched JSON from Corsur CLI examples (MD + episodes JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from githubawesome_lib import (
    categorize_repo,
    episodes_from_titles,
    episodes_payload_window,
    iso_now,
    parse_md_table,
    parse_owner_repo,
    score_repo,
)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
MD_PATH = EXAMPLES / "githubawesome-trending-repos.md"
EP_PATH = EXAMPLES / "githubawesome-trending-repos.json"
DATA_DIR = ROOT / "data"
OUT_JSON = DATA_DIR / "githubawesome-trending-repos-enriched.json"


def main() -> int:
    if not MD_PATH.exists():
        print(f"Missing {MD_PATH}", file=sys.stderr)
        return 1

    rows = parse_md_table(MD_PATH.read_text(encoding="utf-8"))
    episodes = []
    if EP_PATH.exists():
        episodes = episodes_payload_window(json.loads(EP_PATH.read_text(encoding="utf-8")))

    cutoff = "2025-11-26"
    repos_by_url: dict[str, dict] = {}

    for name, url in rows:
        owner, repo = parse_owner_repo(url)
        if not owner:
            continue
        score = score_repo(name, owner, url)
        if score < 2:
            continue
        cats = categorize_repo(name, owner, url)
        if not cats:
            continue
        ep_nums = episodes_from_titles(repo, episodes)
        key = url.lower().rstrip("/")
        dates = [e.get("upload_date") for e in episodes if int(e.get("episode", 0)) in ep_nums]
        first_seen = min(dates) if dates else cutoff
        last_seen = max(dates) if dates else cutoff

        if key in repos_by_url:
            existing = repos_by_url[key]
            existing["categories"] = sorted(set(existing["categories"]) | set(cats))
            existing["episodes"] = sorted(set(existing["episodes"]) | set(ep_nums))
            existing["score"] = max(existing["score"], score)
            existing["last_seen"] = max(existing["last_seen"], last_seen)
            continue

        repos_by_url[key] = {
            "name": repo,
            "url": key,
            "owner": owner,
            "categories": cats,
            "score": score,
            "episodes": ep_nums,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "sources": [
                {
                    "type": "bootstrap",
                    "episode": ep_nums[0] if ep_nums else None,
                    "video_id": next(
                        (
                            e.get("id")
                            for e in episodes
                            if int(e.get("episode", 0)) in ep_nums
                        ),
                        None,
                    ),
                }
            ],
        }

    enriched = {
        "generated_at": iso_now(),
        "cutoff": cutoff,
        "sync_state": {
            "last_sync_at": None,
            "last_sync_status": "idle",
            "last_sync_run_id": None,
            "processed_video_ids": [e.get("id") for e in episodes if e.get("id")],
            "last_episode_number": max((int(e["episode"]) for e in episodes), default=0),
        },
        "episodes": [
            {
                "episode": int(e["episode"]),
                "title": e.get("title"),
                "upload_date": e.get("upload_date"),
                "youtube_url": f"https://www.youtube.com/watch?v={e.get('id')}",
                "video_id": e.get("id"),
            }
            for e in episodes
        ],
        "repos": sorted(
            repos_by_url.values(),
            key=lambda r: (-r["score"], r["name"]),
        ),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(enriched['repos'])} repos to {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
