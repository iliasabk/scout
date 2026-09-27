# ◎ Scout

**An always-on funding agent.** Scout hunts hackathons, grants and bounties while you sleep, filters them through cheap reasoning, scores them against *your* profile and *your* past outcomes, and drafts submission skeletons for the ones worth your time.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) — Personal AI track.

## The problem

Funding you can actually win is scattered across Devpost, grant portals, bounty platforms and listicles that are outdated the day they are published. Finding it is a part-time job: scan, filter, guess fit, miss deadlines, draft from scratch — and do it all again tomorrow, learning nothing. Most indie builders just stop looking.

Scout is the agent that keeps looking.

## What Scout does

Every cycle — on demand from the dashboard, or on the always-on watch loop:

1. **Hunt** — Tavily searches across hackathons, grants, bounties and competitions
2. **Triage** — **Nemotron Nano** filters out dead events and junk (cheap, high volume). Index pages ("Top 40 pitch competitions") are detected as *listicles* and expanded instead of discarded
3. **Expand** — **Nemotron Super** extracts every individual opportunity from a listicle page via Tavily Extract — turning the noisiest pages into the highest-yield source
4. **Score** — **Nemotron Super** scores fit 0–10 against the operator profile, the memory of past outcomes, *and the real track record* (win rate computed from recorded results)
5. **Brief** — a daily brief: top picks, deadlines closing, one lesson from recent outcomes
6. **Draft** — **Nemotron Ultra** writes a submission skeleton for the best fits
7. **Reflect** — **Nemotron Super** reviews the finished cycle and rewrites one of its own skill prompts when the evidence justifies it

Three properties make it a *personal* agent rather than a cron job with an LLM inside:

- **Memory compounds.** Every draft, outcome (won/lost/skipped) and finding is stored and weighed in future scoring — Scout gets better at picking what *you* can win.
- **Skills evolve.** Skills are prompt templates stored in memory. Scout rewrites its own after cycles (self-updates are marked *written by Scout* in the dashboard and are never overwritten by built-ins); you can add new ones at runtime.
- **The track record counts.** Recorded outcomes become a calibration signal — win rate and skipped types are injected into every scoring decision.
## The Nemotron routing

Model IDs are never hardcoded: Scout resolves them live from `GET /models`, so the routing survives catalog rotation.

| Tier | Model (resolved live) | Job |
| --- | --- | --- |
| `nano` | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | triage of dozens of scraped pages per cycle |
| `super` | `nvidia/nemotron-3-super-120b-a12b` | memory-aware fit scoring, daily briefs |
| `ultra` | `nvidia/Nemotron-3-Ultra-550b-a55b` | submission draft skeletons |

All inference runs on **Nebius Token Factory** through its OpenAI-compatible endpoint — the plain `openai` SDK with a swapped `base_url`.

## Quickstart

```bash
cp .env.example .env        # add NEBIUS_API_KEY + TAVILY_API_KEY
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

python run.py once          # one full cycle: hunt → triage → score → brief → draft
python run.py serve         # dashboard on http://localhost:8787
python run.py watch         # always-on: a full cycle every 6 hours
```

## Architecture

```
                ┌────────────────────────────────────────────┐
                │  watch loop (run.py watch, every N hours)  │
                └───────────────┬────────────────────────────┘
                                │
   Tavily search ──► scan ──► triage (Nano) ──► score (Super) ──► brief (Super)
   (hackathons,       pages     live? prize?     fit 0–10 vs        daily brief
   grants, bounties)            deadline?        profile + memory
                                        │
                                        ▼ fit ≥ 7
                                draft skeleton (Ultra)
                                        │
                                        ▼
                 SQLite memory: profile · opportunities · drafts ·
                 outcomes · skills — everything survives restarts
```

## Results from the first production cycles

- **83 opportunities** hunted — 48 from the first scan, more every watch cycle, plus individual items extracted from listicle index pages
- **~30** rejected by the nano tier (dead events, help pages, navigation)
- **10+ shortlisted** with memory-aware fit scores and stated reasoning
- **6 submission skeletons** drafted by the ultra tier (project name, angle, phased build plan, risks, first todos)
- **Scout rewrote its own `draft_submission` skill** after cycle two, citing its own drafts as evidence — the reflect loop is real, visible in the dashboard activity timeline
## Honest feedback on the stack

Feedback on Nebius Token Factory, the Nemotron family and Tavily — required by the hackathon, written from real bugs we hit — lives in [FEEDBACK.md](FEEDBACK.md).

## License

MIT — see [LICENSE](LICENSE).
