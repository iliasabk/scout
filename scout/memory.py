"""Persistent memory — the core of the Personal AI track.

Everything Scout learns survives restarts in one SQLite database:

- profile:       stable facts about the operator (skills, stack, goals, budget)
- memories:      episodic + semantic notes that compound (findings, outcomes)
- opportunities: the working set of hunted funding calls
- submissions:   drafts and their recorded outcomes
- skills:        prompt templates, including ones Scout writes itself
"""
import datetime
import json
import sqlite3

from . import config


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,          -- episodic | semantic | outcome
                content TEXT NOT NULL,
                meta TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT, source TEXT, prize TEXT, deadline TEXT,
                kind TEXT,
                fit_score REAL, why TEXT, angle TEXT,
                status TEXT DEFAULT 'new',   -- new | shortlist | drafting | entered | skipped
                raw TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER NOT NULL,
                draft TEXT, outcome TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                description TEXT,
                prompt TEXT NOT NULL,
                created_at TEXT
            );
            """
        )


# ---- profile ---------------------------------------------------------------

def set_profile(key, value):
    with db() as c:
        c.execute(
            "INSERT INTO profile(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_profile():
    with db() as c:
        rows = c.execute("SELECT key, value FROM profile").fetchall()
    return {r["key"]: r["value"] for r in rows}


def profile_text():
    p = get_profile()
    if not p:
        return "No profile set yet."
    return "\n".join(f"- {k}: {v}" for k, v in sorted(p.items()))


# ---- memories --------------------------------------------------------------

def remember(kind, content, meta=None):
    with db() as c:
        c.execute(
            "INSERT INTO memories(kind, content, meta, created_at) VALUES(?,?,?,?)",
            (kind, content, json.dumps(meta or {}), _now()),
        )


def recent_memories(limit=30):
    with db() as c:
        rows = c.execute(
            "SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def memory_block(limit=30):
    """Recent memory as a text block for prompts."""
    mems = recent_memories(limit)
    if not mems:
        return "No memories yet."
    lines = []
    for m in mems:
        lines.append(f"[{m['created_at'][:10]}] ({m['kind']}) {m['content']}")
    return "\n".join(lines)


# ---- opportunities ---------------------------------------------------------

def upsert_opportunity(url, title, source="", raw=""):
    """Insert if new. Returns (row_id, created_bool)."""
    with db() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO opportunities(url, title, source, raw, created_at) "
            "VALUES(?,?,?,?,?)",
            (url, title, source, raw, _now()),
        )
        created = cur.rowcount > 0
        row = c.execute("SELECT id FROM opportunities WHERE url=?", (url,)).fetchone()
        return (row["id"] if row else None), created


def update_opportunity(opp_id, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with db() as c:
        c.execute(
            f"UPDATE opportunities SET {sets} WHERE id=?", (*fields.values(), opp_id)
        )


def list_opportunities(status=None, limit=200):
    q = "SELECT * FROM opportunities"
    args = []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY COALESCE(fit_score, -1) DESC, id DESC LIMIT ?"
    args.append(limit)
    with db() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_opportunity(opp_id):
    with db() as c:
        row = c.execute("SELECT * FROM opportunities WHERE id=?", (opp_id,)).fetchone()
    return dict(row) if row else None


# ---- submissions -----------------------------------------------------------

def save_submission(opportunity_id, draft, outcome=""):
    with db() as c:
        c.execute(
            "INSERT INTO submissions(opportunity_id, draft, outcome, created_at) "
            "VALUES(?,?,?,?)",
            (opportunity_id, draft, outcome, _now()),
        )


def list_submissions():
    with db() as c:
        rows = c.execute("SELECT * FROM submissions ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ---- skills ----------------------------------------------------------------

def add_skill(name, prompt, description=""):
    with db() as c:
        c.execute(
            "INSERT INTO skills(name, description, prompt, created_at) "
            "VALUES(?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET prompt=excluded.prompt, "
            "description=excluded.description",
            (name, description, prompt, _now()),
        )


def list_skills():
    with db() as c:
        rows = c.execute("SELECT * FROM skills ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_skill(name):
    with db() as c:
        row = c.execute("SELECT * FROM skills WHERE name=?", (name,)).fetchone()
    return dict(row) if row else None


# ---- outcome calibration ----------------------------------------------------

def outcome_stats():
    """Real track record from recorded outcomes — feeds the scoring prompts."""
    with db() as c:
        rows = c.execute(
            "SELECT content FROM memories WHERE kind='outcome' ORDER BY id DESC LIMIT 100"
        ).fetchall()
    total = len(rows)
    if not total:
        return "No completed opportunities recorded yet."
    won = sum(1 for r in rows if ": won" in r["content"].lower())
    lost = sum(1 for r in rows if ": lost" in r["content"].lower())
    skipped = sum(1 for r in rows if ": skipped" in r["content"].lower())
    entered = won + lost
    rate = f" ({won * 100 // entered}% win rate)" if entered else ""
    return (
        f"Track record from memory: {total} outcomes recorded — {won} won, "
        f"{lost} lost, {skipped} skipped{rate}. Weigh similar past opportunities "
        f"accordingly: skipped types are usually a bad fit; won types are a strong signal."
    )
