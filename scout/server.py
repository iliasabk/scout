"""FastAPI dashboard + JSON API for Scout."""
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config, memory, pipeline, skills
from .llm import tf

app = FastAPI(title="Scout", version="0.1.0")


@app.on_event("startup")
def _startup():
    memory.init()
    skills.install_builtins()


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/state")
def state():
    return {
        "profile": memory.get_profile(),
        "opportunities": memory.list_opportunities(limit=100),
        "submissions": memory.list_submissions(),
        "skills": memory.list_skills(),
        "routing": tf.routing_rows() if config.NEBIUS_API_KEY else [],
        "configured": {
            "nebius": bool(config.NEBIUS_API_KEY),
            "tavily": bool(config.TAVILY_API_KEY),
        },
        "recent_memories": memory.recent_memories(40),
        "outcome_stats": memory.outcome_stats(),
        "last_brief": _last_brief(),
    }


def _last_brief():
    for m in memory.recent_memories(60):
        if m["kind"] == "semantic" and (m["content"] or "").startswith("Daily brief generated."):
            return m["content"][len("Daily brief generated."):].strip()
    return ""


class ProfileIn(BaseModel):
    skills: str = ""
    stack: str = ""
    goals: str = ""
    time_budget: str = ""


@app.post("/api/profile")
def set_profile(p: ProfileIn):
    for k, v in p.model_dump().items():
        if v:
            memory.set_profile(k, v)
    memory.remember("semantic", f"Profile updated: {p.model_dump()}")
    return {"ok": True, "profile": memory.get_profile()}


@app.post("/api/scan")
def run_scan():
    result = {}

    def work():
        try:
            result["cycle"] = pipeline.run_cycle()
        except Exception as e:  # surface the failure in the response
            result["error"] = str(e)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=300)
    if "error" in result:
        raise HTTPException(500, result["error"])
    if "cycle" not in result:
        raise HTTPException(504, "scan still running — refresh in a minute")
    return result["cycle"]


@app.post("/api/brief")
def run_brief():
    try:
        return {"brief": pipeline.brief()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/draft/{opp_id}")
def run_draft(opp_id: int):
    try:
        text = pipeline.draft(opp_id)
    except Exception as e:
        raise HTTPException(500, str(e))
    if text is None:
        raise HTTPException(404, "opportunity not found")
    return {"draft": text}


class OutcomeIn(BaseModel):
    outcome: str  # won | lost | skipped


@app.post("/api/outcome/{opp_id}")
def set_outcome(opp_id: int, o: OutcomeIn):
    pipeline.record_outcome(opp_id, o.outcome)
    return {"ok": True}


class SkillIn(BaseModel):
    name: str
    description: str = ""
    prompt: str


@app.post("/api/skills")
def add_skill(s: SkillIn):
    """Write a new skill at runtime — Scout (or you) extends itself."""
    memory.add_skill(s.name, s.prompt, s.description)
    return {"ok": True, "skills": memory.list_skills()}
