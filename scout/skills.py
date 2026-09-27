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
        '"deadline": "<ISO date if stated, else ''>"}}'
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

BUILTINS = [TRIAGE, SCORE_FIT, DAILY_BRIEF, DRAFT_SUBMISSION]


def install_builtins():
    for s in BUILTINS:
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
