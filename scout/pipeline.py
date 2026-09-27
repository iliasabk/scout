"""Scout pipeline: scan → triage → fit-score → brief → draft.

The Nemotron routing is the architecture:
  nano  triages dozens of scraped pages (cheap),
  super scores fit with memory of past outcomes (the workhorse),
  ultra drafts submission skeletons for the top picks (deep reasoning).
"""
import json

from . import config, memory, skills, sources
from .llm import tf


def _extract_json(text):
    """LLMs love wrapping JSON in prose or fences. Fish it out."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def scan(queries=None):
    """Stage 1: hunt pages via Tavily, store new ones."""
    results = sources.scan_all(queries)
    new_ids = []
    for r in results:
        opp_id, created = memory.upsert_opportunity(
            url=r["url"], title=r["title"], source="tavily",
            raw=r["snippet"],
        )
        if created:
            new_ids.append(opp_id)
    print(f"[scan] {len(results)} results, {len(new_ids)} new")
    return new_ids


def triage(opp_id):
    """Stage 2: nano-tier filter. Returns True if it is a live opportunity."""
    opp = memory.get_opportunity(opp_id)
    if not opp:
        return False
    prompt = skills.render(
        "triage", title=opp.get("title") or "", url=opp.get("url") or "",
        snippet=(opp.get("raw") or "")[:1500],
    )
    out = ""
    data = None
    for attempt in (1, 2):  # nano sometimes emits broken JSON — one strict retry
        try:
            out = tf.ask(
                prompt if attempt == 1
                else prompt + "\n\nOutput ONLY valid JSON. No reasoning, no prose.",
                tier="nano", temperature=0.0, max_tokens=1600,
            )
        except Exception as e:
            print(f"[triage] LLM error on #{opp_id} (attempt {attempt}): {e}")
            return False
        data = _extract_json(out)
        if data is not None:
            break
    if data is None:
        print(f"[triage] #{opp_id}: JSON parse failed twice. Raw (300 chars): {out[:300]}")
    data = data or {}
    if not data.get("relevant"):
        memory.update_opportunity(opp_id, status="irrelevant")
        return False
    memory.update_opportunity(
        opp_id,
        title=data.get("title") or opp.get("title"),
        prize=data.get("prize") or "",
        deadline=data.get("deadline") or "",
        kind=data.get("type") or "other",
    )
    return True


def score(opp_id):
    """Stage 3: super-tier fit scoring, memory-aware."""
    opp = memory.get_opportunity(opp_id)
    if not opp:
        return None
    opp_json = json.dumps(
        {k: opp.get(k) for k in ("title", "url", "prize", "deadline", "kind")},
        indent=2,
    )
    prompt = skills.render(
        "score_fit",
        profile=memory.profile_text(),
        memory=memory.memory_block(25),
        opportunity=opp_json,
    )
    out = tf.ask(prompt, tier="super", temperature=0.2, max_tokens=1200)
    data = _extract_json(out) or {}
    fit = data.get("fit_score")
    fit = float(fit) if isinstance(fit, (int, float)) else None
    memory.update_opportunity(
        opp_id,
        fit_score=fit,
        why=data.get("why") or "",
        angle=data.get("angle") or "",
        status="shortlist" if (fit or 0) >= config.DRAFT_THRESHOLD else "scored",
    )
    if fit is not None and fit >= config.DRAFT_THRESHOLD:
        memory.remember(
            "episodic",
            f"Shortlisted '{opp.get('title')}' (fit {fit}/10): {data.get('why', '')}",
            {"opportunity_id": opp_id},
        )
    return fit


def brief():
    """Stage 4: super-tier daily brief over the shortlist."""
    opps = memory.list_opportunities(limit=15)
    opp_lines = []
    for o in opps:
        opp_lines.append(
            f"- {o.get('title')} | prize: {o.get('prize') or '?'} | "
            f"deadline: {o.get('deadline') or '?'} | "
            f"fit: {o.get('fit_score') if o.get('fit_score') is not None else 'unscored'} "
            f"| {o.get('url')}"
        )
    prompt = skills.render(
        "daily_brief",
        profile=memory.profile_text(),
        opportunities="\n".join(opp_lines) or "none yet",
        memory=memory.memory_block(20),
    )
    text = tf.ask(prompt, tier="super", temperature=0.4, max_tokens=1600)
    memory.remember("semantic", f"Daily brief generated.\n{text[:400]}")
    return text


def draft(opp_id):
    """Stage 5: ultra-tier submission skeleton for a top pick."""
    opp = memory.get_opportunity(opp_id)
    if not opp:
        return None
    analysis = json.dumps(
        {"fit_score": opp.get("fit_score"), "why": opp.get("why"),
         "angle": opp.get("angle")},
        indent=2,
    )
    opp_json = json.dumps(
        {k: opp.get(k) for k in ("title", "url", "prize", "deadline", "kind")},
        indent=2,
    )
    prompt = skills.render(
        "draft_submission",
        profile=memory.profile_text(),
        analysis=analysis,
        opportunity=opp_json,
        memory=memory.memory_block(15),
    )
    text = tf.ask(prompt, tier="ultra", temperature=0.4, max_tokens=2800)
    memory.save_submission(opp_id, draft=text)
    memory.update_opportunity(opp_id, status="drafting")
    memory.remember(
        "episodic", f"Drafted submission skeleton for '{opp.get('title')}'.",
        {"opportunity_id": opp_id},
    )
    return text


def record_outcome(opp_id, outcome):
    """The learning loop: record what happened, memory sharpens future scores."""
    opp = memory.get_opportunity(opp_id)
    if not opp:
        return
    memory.remember(
        "outcome",
        f"{opp.get('title')}: {outcome}",
        {"opportunity_id": opp_id, "fit_score": opp.get("fit_score")},
    )
    memory.update_opportunity(opp_id, status="entered" if outcome == "won" else "closed")


def run_cycle(queries=None, drafts=True):
    """Full pass: scan → triage → score → brief (→ drafts for top fits)."""
    new_ids = scan(queries)
    scored = []
    for opp_id in new_ids:
        if triage(opp_id):
            fit = score(opp_id)
            scored.append((opp_id, fit))
    # Draft skeletons for the best new fits.
    if drafts:
        for opp_id, fit in sorted(
            [s for s in scored if s[1] is not None],
            key=lambda s: s[1], reverse=True,
        )[:3]:
            if fit >= config.DRAFT_THRESHOLD:
                draft(opp_id)
    text = brief()
    return {"new": len(new_ids), "triaged": len(scored), "brief": text}
