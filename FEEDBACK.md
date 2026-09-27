# Feedback on the Nebius / NVIDIA / Tavily stack

Written after two days of building Scout against the live APIs — every point below comes from something that actually happened.

## Nebius Token Factory

**Used for:** all inference — chat completions, model discovery, three-tier routing.

**Worked well:**
- The OpenAI-compatible endpoint is genuinely zero-friction: the standard `openai` SDK with a swapped `base_url`. No new client, no new auth flow.
- `GET /models` as the source of truth. Discovering model IDs live instead of hardcoding them saved us when we saw how the catalog is rotated — this should be the canonical pattern for every integration.

**Needs work:**
- The `list_models` response has no metadata beyond IDs (context window, modality, price tier). We had to pattern-match names to build routing tiers; a structured capability field would make routing a config choice instead of string matching.
- No documented way to disable thinking per call on Nemotron models (see below), which matters a lot for cost and latency on high-volume classification.

**Would we build on it again?** Yes — the endpoint did its job invisibly for hundreds of calls across two days.

## NVIDIA Nemotron 3 family

**Nano 30B:** fast and cheap enough to throw at dozens of pages per cycle, which is exactly what the triage tier needed. Two real problems: (1) as reasoning models, they spend `max_tokens` on thinking before the answer — our first triage calls with a 400-token budget returned *empty content* and silently failed as "not relevant"; raising the budget to 1600 fixed it, but the failure mode was invisible until we logged raw outputs. A reasoning/off switch or a documented thinking budget would remove this class of bug entirely. (2) strict-JSON compliance is maybe ~85% — occasionally truncated or quoted-broken JSON. A strict retry with an "ONLY valid JSON" instruction recovered almost every failure, but native JSON mode / structured output on Token Factory would delete that whole workaround.

**Super 120B:** the workhorse. Fit scoring with profile + memory context produced consistently sensible, honest judgments ("a bad fit wastes days of build time" is literally in the prompt, and the scores behaved accordingly). Structured output was reliable at this size.

**Ultra 550B:** the drafts it wrote were the most impressive single output of the project — phased build plans with day estimates, risks, and first todos, specific to each opportunity. Slow, but that is what the routing is for: it runs three times per cycle, not thirty.
## Tavily

**Worked well:** search quality on niche funding queries is strong — it surfaced an active $138K hackathon that manual research had missed. The `/extract` endpoint is a clean way to pull readable page content.

**Needs work:** listicle pages ("The Top 40 Startup Pitch Competitions of 2026") come back as one result — a page about forty opportunities is not one opportunity. Our triage had to learn to reject them, which throws away the most information-dense pages in the index. A structured-results mode for list pages would turn them into the highest-yield source in the pipeline.

## What we would want next

1. A per-call `thinking: on/off` (or reasoning-effort) parameter on Token Factory
2. JSON mode / structured outputs on Nemotron models
3. Token usage broken down into reasoning vs. output tokens
4. Model metadata (context, modality, price) in `GET /models`

## Bottom line

The three-tier pattern — cheap reasoning to filter, mid reasoning to judge, deep reasoning to create — is the entire architecture, and it only works because all three sizes are behind one OpenAI-compatible endpoint. That is the real win of Token Factory for agent builders.
