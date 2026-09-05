"""Find rich product-detail structures (highlights, specifications, reviews,
image galleries) inside captured HAR JSON responses, and print samples so we
know how to extract them per site."""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

SPEC_KEYS = re.compile(r"(specificat|technicaldetail|productdetail|attribute)", re.I)
HL_KEYS = re.compile(r"(highlight|keyfeature|bullet)", re.I)
REV_KEYS = re.compile(r"(review)", re.I)
IMG_KEYS = re.compile(r"(images|gallery|imagelist|photos)", re.I)


def _text(entry: dict) -> str:
    c = entry.get("response", {}).get("content", {}) or {}
    t = c.get("text") or ""
    if c.get("encoding") == "base64":
        try:
            return base64.b64decode(t).decode("utf-8", "replace")
        except Exception:
            return ""
    return t


def _short(v: Any, n: int = 200) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s[:n].replace("\n", " ")


def scan(path: str) -> None:
    print(f"\n===== {Path(path).name} =====")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print("  parse error:", e)
        return
    hits = {"spec": [], "highlight": [], "review": [], "imggallery": []}
    for e in data.get("log", {}).get("entries", []):
        if "json" not in (e.get("response", {}).get("content", {}) or {}).get("mimeType", ""):
            continue
        txt = _text(e)
        if not txt:
            continue
        # cheap prefilter
        low = txt.lower()
        if not any(w in low for w in ("specific", "highlight", "review", "rating", "feature")):
            continue
        try:
            root = json.loads(txt)
        except ValueError:
            continue
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for k, v in node.items():
                    if SPEC_KEYS.search(k) and v and len(hits["spec"]) < 3:
                        hits["spec"].append(f"[{k}] " + _short(v, 300))
                    elif HL_KEYS.search(k) and v and len(hits["highlight"]) < 3:
                        hits["highlight"].append(f"[{k}] " + _short(v, 300))
                    elif REV_KEYS.search(k) and isinstance(v, (list, dict)) and v and len(hits["review"]) < 3:
                        hits["review"].append(f"[{k}] " + _short(v, 400))
                    elif IMG_KEYS.search(k) and isinstance(v, list) and len(v) > 1 and len(hits["imggallery"]) < 2:
                        hits["imggallery"].append(f"[{k}] " + _short(v, 250))
                    stack.append(v)
            elif isinstance(node, list):
                stack.extend(node)
    for kind, samples in hits.items():
        print(f"  -- {kind}: {len(samples)} sample(s)")
        for s in samples:
            print("     ", s)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        scan(p)
