#!/usr/bin/env python3
"""Search the web with the operator's Serper key; results are leads, not evidence."""

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


URL = "https://google.serper.dev/search"


def search(query, api_key, limit=10):
    if not api_key:
        raise ValueError("Set SERPER_API_KEY in your environment before searching")
    request = urllib.request.Request(
        URL,
        data=json.dumps({"q": query, "num": limit}).encode("utf-8"),
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("organic"), list):
        raise ValueError("Serper response has no organic results list")
    results = []
    for item in payload["organic"]:
        if not isinstance(item, dict):
            continue
        link = item.get("link", "")
        if not isinstance(link, str) or urlparse(link).scheme not in ("http", "https") or not urlparse(link).netloc:
            continue
        results.append({
            "title": str(item.get("title") or "")[:300],
            "url": link,
            "snippet": str(item.get("snippet") or "")[:1000],
        })
    return {"query": query, "status": "results" if results else "empty", "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Search query for sources or relevant coverage")
    parser.add_argument("--out", required=True, type=Path, help="Private JSON output path, outside Git")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or not args.query.strip():
        parser.error("Provide a non-empty query and --limit between 1 and 100")
    try:
        result = search(args.query, os.environ.get("SERPER_API_KEY", ""), args.limit)
    except (ValueError, urllib.error.URLError) as exc:
        parser.exit(1, f"Search failed: {exc}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(result['results'])} search leads to {args.out}")


if __name__ == "__main__":
    main()
