"""One-off: mark later duplicate titles as skipped (keeps the first)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scout import memory

seen = {}
n = 0
for o in memory.list_opportunities(limit=2000):
    t = " ".join((o["title"] or "").lower().split())
    if t and t in seen and o["status"] not in ("irrelevant", "skipped"):
        memory.update_opportunity(o["id"], status="skipped")
        n += 1
    elif t:
        seen[t] = o["id"]
print("duplicates skipped:", n)
