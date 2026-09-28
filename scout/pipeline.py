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
    if data.get("listicle"):
        # A page ABOUT many opportunities is not one opportunity — expand it.
        extract_listicle(opp_id)
        memory.update_opportunity(opp_id, status="expanded")
        return False
    return True


def extract_listicle(opp_id):
    """Expand an index page ('Top 40 ...') into individual opportunities."""
    opp = memory.get_opportunity(opp_id)
    if not opp:
        return []
    try:
        pages = sources.tavily_extract([opp.get("url")])
    except Exception as e:
        print(f"[extract] #{opp_id} extract failed: {e}")
        return []
    content = (pages.get(opp.get("url")) or "")[:12000]
    if len(content) < 400:
        return []
    prompt = skills.render(
        "extract_listicle",
        title=opp.get("title") or "", url=opp.get("url") or "",
        content=content,
    )
    out = tf.ask(prompt, tier="super", temperature=0.0, max_tokens=2800)
    data = _extract_json(out)
    if not isinstance(data, list):
        return []
    created, scored = [], 0
    for item in data[:15]:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        if memory.find_by_title(item.get("title")):
            continue  # same title already hunted — no duplicates
        url = item.get("url") or (
            (opp.get("url") or "listicle") + "#" + item.get("title", "")[:40].replace(" ", "-")
        )
        new_id, was_new = memory.upsert_opportunity(
            url=url, title=item.get("title"), source="listicle:" + str(opp_id),
            raw=str(item)[:500],
        )
        if not was_new:
            continue
        memory.update_opportunity(
            new_id,
            prize=item.get("prize") or "",
            deadline=item.get("deadline") or "",
            kind=item.get("kind") or "other",
        )
        created.append(new_id)
        # Items come from a curated super-tier extraction — score them directly,
        # skipping past deadlines.
        dl = (item.get("deadline") or "")[:10]
        if dl and dl < "2026-09-27":
            memory.update_opportunity(new_id, status="skipped")
            continue
        if scored < 10:
            score(new_id)
            scored += 1
    if created:
        memory.remember(
            "episodic",
            f"Expanded listicle '{opp.get('title')}' into {len(created)} opportunities.",
            {"source_opportunity": opp_id},
        )
        print(f"[extract] #{opp_id} expanded into {len(created)} opportunities")
    return created


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
        memory=memory.memory_block(25) + "\n\n" + memory.outcome_stats(),
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
    memory.remember("semantic", "Daily brief generated.\n" + text)
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


def _cycle_report():
    """What the agent knows about its own last performance."""
    os_ = memory.list_opportunities(limit=500)
    counts = {}
    for o in os_:
        counts[o["status"] or "new"] = counts.get(o["status"] or "new", 0) + 1
    shortlist = [
        {"title": o["title"], "fit": o["fit_score"], "why": (o["why"] or "")[:120]}
        for o in os_ if o["status"] in ("shortlist", "drafting") and o["fit_score"]
    ][:8]
    return {
        "opportunities_by_status": counts,
        "recent_shortlist": shortlist,
        "recent_memory": memory.memory_block(10),
    }


def reflect():
    """After a cycle: review performance and improve one skill (self-evolution)."""
    skills_text = "\n\n".join(
        f"--- {s['name']} ---\n{s['prompt']}" for s in memory.list_skills()
    )
    prompt = skills.render(
        "reflect", skills=skills_text,
        report=json.dumps(_cycle_report(), indent=2),
    )
    out = tf.ask(prompt, tier="super", temperature=0.3, max_tokens=2400)
    data = _extract_json(out) or {}
    action = data.get("action")
    if action in ("update", "create") and data.get("skill") and data.get("prompt"):
        memory.add_skill(
            data["skill"], data["prompt"], "[scout] " + (data.get("reason") or "")
        )
        memory.remember(
            "episodic",
            f"Self-update: {action}d skill '{data['skill']}' — {data.get('reason', '')}",
        )
        print(f"[reflect] {action}d skill '{data['skill']}': {data.get('reason', '')}")
        return data
    print(f"[reflect] no skill change: {data.get('reason') or 'none justified'}")
    return data


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
    try:
        reflect()
    except Exception as e:
        print(f"[reflect] failed (continuing): {e}")
    return {"new": len(new_ids), "triaged": len(scored), "brief": text}
