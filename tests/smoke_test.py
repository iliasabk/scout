"""Offline smoke test: full Nemotron pipeline without Tavily.

Seeds one known opportunity (the Nebius x NVIDIA hackathon itself), runs
triage (nano tier) and fit scoring (super tier) against the live Token
Factory API, and prints what came back. Run from the project root:

    .venv/Scripts/python tests/smoke_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scout import memory, pipeline, skills
from scout.llm import tf

SEED = {
    "url": "https://nebiusglobalaihackathon.devpost.com/",
    "title": "Nebius x NVIDIA Global AI Hackathon",
    "snippet": (
        "$50,000+ in prizes. Grand prize $20,000 cash. Build a working AI system "
        "on Nebius Token Factory or AI Cloud using at least one NVIDIA open source "
        "model. Tracks: Coding and Agentic Engineering, Best Apps and Agents, "
        "Personal AI, Physical AI. Submissions close October 30, 2026."
    ),
}

STARTER_PROFILE = {
    "skills": "solo developer, fast AI prototyping, shipping working demos",
    "stack": "Python, JavaScript/Node, LLM agents, video pipelines",
    "goals": "win hackathon prize money with focused, high-quality submissions",
    "time_budget": "up to 20h/week",
}


def main():
    memory.init()
    skills.install_builtins()
    print("skills:", [s["name"] for s in memory.list_skills()])

    if not memory.get_profile():
        for k, v in STARTER_PROFILE.items():
            memory.set_profile(k, v)
        print("profile seeded (editable in the dashboard)")

    opp_id, created = memory.upsert_opportunity(
        url=SEED["url"], title=SEED["title"], source="seed", raw=SEED["snippet"],
    )
    print(f"opportunity #{opp_id} ({'new' if created else 'existing'})")

    print("\n-- triage (nano tier) --")
    live = pipeline.triage(opp_id)
    print("relevant:", live)
    if live:
        opp = memory.get_opportunity(opp_id)
        print("parsed:", json.dumps(
            {k: opp.get(k) for k in ("title", "prize", "deadline", "kind")}, indent=2,
        ))

        print("\n-- score (super tier) --")
        fit = pipeline.score(opp_id)
        print("fit:", fit)

    print("\n-- routing --")
    for row in tf.routing_rows():
        print(f"  {row['tier']}: {row['model']}")


if __name__ == "__main__":
    main()
