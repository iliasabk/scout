"""Token Factory client — OpenAI-compatible inference on Nebius.

Two properties matter for the hackathon:

1. One client, three Nemotron tiers. Callers ask for a tier ("nano",
   "super", "ultra") and this class maps it to a concrete model.
2. Model IDs are discovered live via GET /models, never hardcoded. If the
   catalog rotates a model out, Scout degrades to the fallback instead of
   crashing mid-scan.
"""
import threading

from openai import OpenAI

from . import config


class TokenFactory:
    def __init__(self):
        self._client = None
        self._models = None
        self._tiers = {}
        self._lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            if not config.NEBIUS_API_KEY:
                raise RuntimeError(
                    "NEBIUS_API_KEY is not set. Copy .env.example to .env and "
                    "add your key from https://tokenfactory.nebius.com"
                )
            self._client = OpenAI(
                base_url=config.NEBIUS_BASE_URL,
                api_key=config.NEBIUS_API_KEY,
            )
        return self._client

    def models(self):
        """Live GET /models — the source of truth for routing."""
        if self._models is None:
            with self._lock:
                if self._models is None:
                    self._models = sorted(m.id for m in self.client.models.list())
                    self._tiers = self._resolve_tiers()
        return self._models

    def _resolve_tiers(self):
        tiers = {}
        for tier, needles in config.TIER_PATTERNS.items():
            matches = [
                m for m in self._models
                if all(n in m.lower() for n in needles)
            ]
            if matches:
                tiers[tier] = sorted(matches)[0]
        return tiers

    def model_for(self, tier):
        """Map a routing tier to a live model ID."""
        self.models()
        return self._tiers.get(tier, config.FALLBACK_MODEL)

    def routing_rows(self):
        self.models()
        return [
            {"tier": tier, "model": self._tiers.get(tier, config.FALLBACK_MODEL)}
            for tier in ("nano", "super", "ultra")
        ]

    def chat(self, messages, tier="super", tools=None, temperature=0.2,
             max_tokens=2048):
        kwargs = dict(
            model=self.model_for(tier),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message

    def ask(self, prompt, tier="super", system=None, temperature=0.2,
            max_tokens=2048):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        msg = self.chat(messages, tier=tier, temperature=temperature,
                        max_tokens=max_tokens)
        content = msg.content or ""
        if not content.strip():
            # Reasoning models sometimes put everything in reasoning_content.
            extra = msg.model_extra or {}
            for key in ("reasoning_content", "reasoning"):
                val = extra.get(key)
                if isinstance(val, str) and val.strip():
                    content = val
                    break
        return content.strip()


tf = TokenFactory()
