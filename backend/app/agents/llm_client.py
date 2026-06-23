import json
import time
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Unified LLM client supporting Anthropic Claude and OpenAI, with mock fallback."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._clients: dict[str, Any] = {}

    def _has_live_credentials(self) -> bool:
        if self.settings.use_mock_llm:
            return False
        if self.settings.llm_provider == "anthropic":
            return bool(self.settings.anthropic_api_key)
        if self.settings.llm_provider == "openai":
            return bool(self.settings.openai_api_key)
        return False

    def _get_client(self, model: Optional[str] = None):
        model = model or self.settings.llm_model
        if model in self._clients:
            return self._clients[model]

        if not self._has_live_credentials():
            return None

        if self.settings.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            client = ChatAnthropic(
                model=model,
                temperature=self.settings.llm_temperature,
                api_key=self.settings.anthropic_api_key,
            )
        elif self.settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI

            client = ChatOpenAI(
                model=model,
                temperature=self.settings.llm_temperature,
                api_key=self.settings.openai_api_key,
            )
        else:
            return None

        self._clients[model] = client
        return client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        agent: str = "default",
        model: Optional[str] = None,
    ) -> tuple[str, float, float]:
        """Returns (response_text, latency_ms, cost_usd)."""
        effective_model = model or self.settings.llm_model
        start = time.perf_counter()
        client = self._get_client(effective_model)

        if client is None:
            response = self._mock_response(agent, user_prompt)
            latency = (time.perf_counter() - start) * 1000
            return response, latency, 0.0

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        result = await client.ainvoke(messages)
        latency = (time.perf_counter() - start) * 1000
        cost = self._estimate_cost(
            len(system_prompt) + len(user_prompt),
            len(result.content),
            model=effective_model,
        )
        return result.content, latency, cost

    def _estimate_cost(self, input_chars: int, output_chars: int, model: Optional[str] = None) -> float:
        # Rough per-char estimates from Anthropic list pricing (USD / char ≈ price per MTok / 1e6)
        model = (model or self.settings.llm_model or "").lower()
        if self.settings.llm_provider == "anthropic":
            if "haiku" in model:
                input_rate, output_rate = 0.0000001, 0.0000005  # ~$1 / $5 per MTok
            elif "sonnet" in model:
                input_rate, output_rate = 0.0000003, 0.0000015  # ~$3 / $15 per MTok
            elif "opus" in model:
                input_rate, output_rate = 0.0000015, 0.0000075
            else:
                input_rate, output_rate = 0.00000025, 0.00000125
            return (input_chars * input_rate) + (output_chars * output_rate)
        return (input_chars * 0.00000015) + (output_chars * 0.0000006)

    def _mock_response(self, agent: str, user_prompt: str) -> str:
        """Deterministic mock responses for testing without API keys."""
        if "extract" in agent.lower() or "Extract atomic" in user_prompt[:50]:
            return json.dumps({
                "claims": [
                    {"subject": "India", "predicate": "won", "object": "Cricket World Cup", "timestamp": "2011-04-02", "weight": 1.0},
                    {"subject": "India Cricket World Cup win", "predicate": "year", "object": "2011", "timestamp": "2011-04-02", "weight": 0.8},
                    {"subject": "India Cricket World Cup 2011 team", "predicate": "captain", "object": "MS Dhoni", "timestamp": None, "weight": 0.7},
                ]
            })

        if agent == "advocate":
            return json.dumps({
                "reasoning": "The retrieved evidence supports the claim. Multiple sources confirm the factual assertion with consistent details.",
                "confidence": 0.82,
                "sources": ["source-1"],
                "evidence_used": ["evidence-1"],
            })

        if agent == "skeptic":
            return json.dumps({
                "reasoning": "While evidence appears supportive, there are potential weaknesses in source credibility and temporal specificity.",
                "confidence": 0.35,
                "challenges": [
                    {
                        "challenge_type": "weak_evidence",
                        "description": "Primary evidence lacks independent corroboration",
                        "reasoning": "Only one high-credibility source directly addresses this specific claim",
                        "evidence_refs": [],
                        "confidence": 0.4,
                    },
                    {
                        "challenge_type": "missing_context",
                        "description": "Context around qualifying conditions is absent",
                        "reasoning": "The claim may be true in a narrow sense but misleading without qualifiers",
                        "evidence_refs": [],
                        "confidence": 0.3,
                    },
                ],
                "sources": [],
            })

        if agent == "judge":
            return json.dumps({
                "verdict": "supported",
                "confidence": 0.78,
                "reasoning": "The Advocate presents stronger evidence-backed arguments. The Skeptic raises valid concerns about context but fails to refute the core claim.",
                "evidence_used": ["evidence-1"],
            })

        return json.dumps({"reasoning": "Mock response", "confidence": 0.5})


def parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise
