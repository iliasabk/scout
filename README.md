# Scout — the always-on funding agent

**Scout hunts prize money for you while you build.** It continuously scans
hackathons, grants, bounties and competitions, triages them, scores them
against your personal profile, remembers every submission and outcome, drafts
application skeletons, and briefs you every morning on what is actually worth
your time.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) — Personal AI track.

## Why

Winning funding is a part-time job: platforms scatter opportunities across
Devpost, grant portals, bounty boards and sponsor blogs; deadlines slip;
applications go out to competitions you never had a realistic chance of
winning. Scout turns that into a background process. The more you use it, the
better it targets: every submission result is written to persistent memory and
feeds back into the fit-scoring of the next opportunity.

## How it works

```
                 ┌────────────────────────────────────────────────┐
                 │                    SCOUT                        │
Tavily search ──▶│  scan ─▶ triage ─▶ fit-score ─▶ brief ─▶ draft  │
  (web)          │         Nemotron  Nemotron   Nemotron  Nemotron │
                 │          Nano      Super      Super     Ultra   │
                 │        (cheap,    (routing,  (memory-  (deep    │
                 │         fast)      honest)     aware)   drafts)  │
                 └───────────────┬─────────────────────────────────┘
                                 │
              SQLite persistent memory (profile, episodes,
              outcomes, opportunities, self-written skills)
```

**Model routing is the architecture.** Everything on Nebius Token Factory,
OpenAI-compatible:

| Stage | Model tier | Why |
| --- | --- | --- |
| Triage: "is this page a live, open, prize-bearing opportunity?" | Nemotron Nano | Cheap classification of dozens of scraped results |
| Fit scoring against your profile + past outcomes | Nemotron Super | Honest judgment, the workhorse |
| Daily brief | Nemotron Super | Synthesis with memory |
| Application skeleton for the top picks | Nemotron Ultra | Long-form reasoning and drafting |

The model IDs are **not hardcoded**: Scout calls `GET /models` at startup and
pattern-matches the Nemotron family into tiers, so it survives catalog
changes. Web research runs through Tavily (`search` + `extract`).

## Install

```bash
git clone <repo-url> && cd scout
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add NEBIUS_API_KEY + TAVILY_API_KEY
```

Get the keys:

- **Nebius Token Factory**: <https://tokenfactory.nebius.com> (hackathon participants: use event code `NEBIUS-DEVPOST-GLOBAL26` for $25 in credits, plus $25 via the Nebius Builders Program)
- **Tavily**: <https://app.tavily.com> (free tier: 1,000 search credits/month)

## Run

```bash
# one full cycle: scan → triage → score → brief
python run.py once

# scan only / brief only
python run.py scan
python run.py brief

# live dashboard on http://localhost:8787
python run.py serve
```

First run: set your profile in the dashboard (skills, stack, goals, time
budget). Scout stores it in persistent memory and every later stage reads it.

## The compounding loop

1. **Scan** — Tavily queries across hackathon/grant/bounty sources.
2. **Triage** — Nemotron Nano filters dead pages and non-opportunities.
3. **Fit score** — Nemotron Super scores 0–10 against profile **and the
   memory of every past submission and its outcome**. "You scored 2/10 on the
   last three web3 bounties; here is another one" should not happen twice.
4. **Daily brief** — what is new, what is closing, what fits, what to ignore.
5. **Draft** — for top picks, Nemotron Ultra writes the submission skeleton:
   project angle, track mapping, build plan, first three todos.
6. **Learn** — you record the outcome (won / lost / skipped); it becomes
   episodic memory that sharpens the next fit score.

## Deploy to Nebius Serverless (optional, demo URL)

The whole app is a FastAPI service, so it deploys as-is into a Nebius
Serverless endpoint (container port 8787) — one container, SQLite volume,
Token Factory and Tavily via environment variables. See
`nebius ai endpoint create` in the Nebius CLI; a ready-to-use deploy script is
in `deploy/`.

## Project layout

```
run.py              CLI: scan | brief | once | serve
scout/
  config.py         env, model-tier patterns, source queries
  llm.py            Token Factory client (live /models discovery + tier routing)
  memory.py         SQLite persistent memory (profile, episodes, outcomes, skills)
  skills.py         reusable skills (built-ins + self-written at runtime)
  sources.py        Tavily search + extract
  pipeline.py       scan → triage → score → brief → draft
  server.py         FastAPI dashboard
static/index.html   single-file dashboard UI
```

## License

MIT — see [LICENSE](LICENSE).
