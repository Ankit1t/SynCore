"""Scan a HAR file: summarize entries by mime type and flag product/image data."""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def scan(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    entries = data.get("log", {}).get("entries", [])
    print(f"\n===== {Path(path).name}  ({len(entries)} entries) =====")
    by_mime: collections.Counter = collections.Counter()
    html_docs = []
    json_apis = []
    img_hosts: collections.Counter = collections.Counter()
    for e in entries:
        req = e.get("request", {})
        resp = e.get("response", {})
        url = req.get("url", "")
        mime = (resp.get("content", {}) or {}).get("mimeType", "") or ""
        by_mime[mime.split(";")[0]] += 1
        size = (resp.get("content", {}) or {}).get("size", 0)
        if "text/html" in mime and size > 20000:
            html_docs.append((size, url[:110]))
        if "json" in mime and size > 2000:
            json_apis.append((size, url[:110]))
        if "image" in mime:
            host = url.split("/")[2] if "//" in url else url[:40]
            img_hosts[host] += 1
    print("-- mime types --")
    for m, c in by_mime.most_common(12):
        print(f"   {c:5d}  {m}")
    print("-- big HTML docs (top 6) --")
    for size, url in sorted(html_docs, reverse=True)[:6]:
        print(f"   {size:>9}  {url}")
    print("-- big JSON responses (top 8) --")
    for size, url in sorted(json_apis, reverse=True)[:8]:
        print(f"   {size:>9}  {url}")
    print("-- image hosts --")
    for h, c in img_hosts.most_common(6):
        print(f"   {c:5d}  {h}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        scan(p)
