"""Reusable skills.

Skills are prompt templates with a job. Built-ins ship with Scout; new ones
can be written at runtime by the agent or the operator (they land in the
skills table via memory.add_skill) — that is the "self-written skills"
requirement of the Personal AI track.
"""
from . import memory

# ---- built-in skills --------------------------------------------------------

TRIAGE = {
    "name": "triage",
    "description": "Cheap filter: is this scraped page a live, open, prize-bearing opportunity?",
    "prompt": (
        "You filter funding opportunities for an agent called Scout. "
        "Given a scraped web result, decide if it is a LIVE opportunity with "
        "prize money that is open for entries right now. If the event year is "
        "in the past (for example 2025) or its deadline has already passed, "
        "relevant must be false.\n\n"
        "Result:\nTitle: {title}\nURL: {url}\nSnippet: {snippet}\n\n"
        "Answer with strict JSON only, no prose:\n"
        '{{"relevant": true/false, "type": "hackathon|grant|bounty|competition|other", '
        '"title": "<cleaned official title>", "prize": "<prize pool or '' if none>", '
        '"deadline": "<ISO date if stated, else ''>", '
        '"listicle": <true if this page LISTS multiple opportunities instead of being one>}}'
    ),
}

SCORE_FIT = {
    "name": "score_fit",
    "description": "Honest fit scoring of an opportunity against the operator profile and past outcomes.",
    "prompt": (
        "You are Scout. You match funding opportunities to your operator and you are "
        "brutally honest: a bad fit wastes days of build time.\n\n"
        "OPERATOR PROFILE:\n{profile}\n\n"
        "RECENT MEMORY (past submissions, outcomes, lessons):\n{memory}\n\n"
        "OPPORTUNITY:\n{opportunity}\n\n"
        "Score the fit from 0 to 10. Past outcomes weigh heavily: if similar "
        "opportunities were skipped, lost or scored low before, say so and "
        "score accordingly.\n\n"
        "Answer with strict JSON only, no prose:\n"
        '{{"fit_score": <0-10>, "why": "<two sentences max>", '
        '"angle": "<if fit>=6: the sharpest angle to win; else empty>"}}'
    ),
}

DAILY_BRIEF = {
    "name": "daily_brief",
    "description": "Morning brief: what is new, what is closing, what is worth it.",
    "prompt": (
        "You are Scout. Write today's brief for your operator.\n\n"
        "OPERATOR PROFILE:\n{profile}\n\n"
        "OPPORTUNITIES (best first):\n{opportunities}\n\n"
        "RECENT MEMORY:\n{memory}\n\n"
        "Write tight Markdown, max 250 words: (1) top 3 picks worth time and "
        "why, (2) deadlines closing within 7 days, (3) one lesson from recent "
        "outcomes. No fluff, no restating the obvious."
    ),
}

DRAFT_SUBMISSION = {
    "name": "draft_submission",
    "description": "Submission skeleton for a top pick: angle, plan, first todos.",
    "prompt": (
        "You are Scout. Your operator is entering this opportunity and you "
        "draft the submission skeleton.\n\n"
        "OPERATOR PROFILE:\n{profile}\n\n"
        "FIT ANALYSIS:\n{analysis}\n\n"
        "OPPORTUNITY:\n{opportunity}\n\n"
        "RELEVANT MEMORY:\n{memory}\n\n"
        "Produce Markdown with: (1) project name + one-liner, (2) the winning "
        "angle, (3) build plan in phases with time estimates in days, "
        "(4) risks and how to cut them, (5) the first three concrete todos. "
        "Be specific to this opportunity — nothing generic."
    ),
}

EXTRACT_LISTICLE = {
    "name": "extract_listicle",
    "description": "Expand a page that lists many opportunities into individual opportunities.",
    "prompt": (
        "You extract funding opportunities from a web page for an agent called Scout.\n\n"
        "PAGE TITLE: {title}\nPAGE URL: {url}\n\n"
        "PAGE CONTENT (truncated):\n{content}\n\n"
        "Extract EVERY distinct opportunity mentioned (hackathon, grant, bounty, "
        "competition) as strict JSON only, no prose:\n"
        '[{{"title": "<official name>", "url": "<link if present, else empty>", '
        '"prize": "<prize pool or empty>", "deadline": "<ISO date if stated, else empty>", '
        '"kind": "hackathon|grant|bounty|competition"}}]\n\n'
        "Rules: maximum 15 items, most attractive first. Skip closed/past events, "
        "navigation items, and anything that is not itself an opportunity."
    ),
}

REFLECT = {
    "name": "reflect",
    "description": "After each cycle: review what failed and improve one skill prompt.",
    "prompt": (
        "You are Scout, an always-on funding agent. After a hunting cycle you "
        "reflect on your own performance and improve ONE of your skills.\n\n"
        "CURRENT SKILLS:\n{skills}\n\n"
        "CYCLE REPORT:\n{report}\n\n"
        "If a concrete, evidence-based improvement is justified, update one skill "
        "prompt or write a new skill. Preserve every {{placeholder}} field the "
        "skill's pipeline expects (triage needs title/url/snippet; score_fit needs "
        "profile/memory/opportunity; daily_brief needs profile/opportunities/memory; "
        "draft_submission needs profile/analysis/opportunity/memory).\n\n"
        "Answer with strict JSON only, no prose:\n"
        '{{"action": "update|create|none", "skill": "<name>", '
        '"prompt": "<the full new prompt template, or empty>", '
        '"reason": "<one sentence, cite the evidence>"}}'
    ),
}

BUILTINS = [TRIAGE, SCORE_FIT, DAILY_BRIEF, DRAFT_SUBMISSION, EXTRACT_LISTICLE, REFLECT]


def install_builtins():
    """Seed built-in skills — never overwrite a version the agent wrote itself."""
    for s in BUILTINS:
        row = memory.get_skill(s["name"])
        if row and (row.get("description") or "").startswith("[scout]"):
            continue
        memory.add_skill(s["name"], s["prompt"], s["description"])


def render(skill_name, **fields):
    """Load a skill (DB first, built-ins as fallback) and fill its template."""
    row = memory.get_skill(skill_name)
    template = row["prompt"] if row else None
    if template is None:
        for s in BUILTINS:
            if s["name"] == skill_name:
                template = s["prompt"]
                break
    if template is None:
        raise KeyError(f"unknown skill: {skill_name}")
    try:
        return template.format(**fields)
    except KeyError as e:
        raise KeyError(
            f"skill '{skill_name}' is missing a template field: {e}"
        ) from None
