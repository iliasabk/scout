"""Configuration for Scout.

Everything that can change lives in the environment (see .env.example).
Model IDs are intentionally NOT hardcoded here: the Token Factory catalog
changes, so llm.py resolves the Nemotron family live from GET /models.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is in requirements but optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "scout.db"
STATIC_DIR = BASE_DIR / "static"

NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
SCOUT_PORT = int(os.environ.get("SCOUT_PORT", "8787"))

# Routing tiers: which Nemotron variant handles which kind of work.
# Patterns are matched (case-insensitive, all-terms) against live model IDs.
TIER_PATTERNS = {
    "nano": ["nemotron", "nano"],    # cheap classification of scraped results
    "super": ["nemotron", "super"],  # fit scoring, briefs (the workhorse)
    "ultra": ["nemotron", "ultra"],  # long-form reasoning, submission drafts
}
# Used when a tier cannot be resolved from the live catalog.
FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# Where Scout hunts. Rotate these freely — they are just Tavily queries.
DEFAULT_QUERIES = [
    "active hackathon 2026 prize money open for registration",
    "developer hackathon devpost open now cash prizes",
    "open source bounty program open 2026 rewards",
    "startup competition 2026 open for applications prize money",
    "AI grant program 2026 open call developers",
    "web3 hackathon 2026 prize pool open registration",
]

# How many Tavily results per query.
SCAN_MAX_RESULTS = 8
# Fit scores >= this get a draft skeleton from the Ultra tier.
DRAFT_THRESHOLD = 7.0
