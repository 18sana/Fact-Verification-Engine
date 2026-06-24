from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import AdvocateAgent, ClaimExtractionAgent, JudgeAgent, SkepticAgent
from app.core.logging import get_logger
from app.domain.enums import Verdict
from app.domain.models import AgentContext, AgentResponse, AtomicClaim, Evidence

logger = get_logger(__name__)


class VerificationState(TypedDict, total=False):
    claim_text: str
    atomic_claims: list[AtomicClaim]
    evidence: list[Evidence]
    advocate_response: AgentResponse
    skeptic_response: AgentResponse
    judge_response: AgentResponse
    overall_verdict: str
    overall_confidence: float
    requires_human_review: bool
    error: str


class VerificationWorkflow:
    """LangGraph orchestration for multi-agent verification."""

    def __init__(
        self,
        claim_extractor: ClaimExtractionAgent | None = None,
        advocate: AdvocateAgent | None = None,
        skeptic: SkepticAgent | None = None,
        judge: JudgeAgent | None = None,
        human_review_threshold: float = 0.6,
    ):
        self.claim_extractor = claim_extractor or ClaimExtractionAgent()
        self.advocate = advocate or AdvocateAgent()
        self.skeptic = skeptic or SkepticAgent()
        self.judge = judge or JudgeAgent()
        self.human_review_threshold = human_review_threshold
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(VerificationState)

        workflow.add_node("extract_claims", self._extract_claims)
        workflow.add_node("check_evidence", self._check_evidence)
        workflow.add_node("advocate", self._run_advocate)
        workflow.add_node("skeptic", self._run_skeptic)
        workflow.add_node("judge", self._run_judge)
        workflow.add_node("insufficient_evidence", self._insufficient_evidence)

        workflow.set_entry_point("extract_claims")
        workflow.add_edge("extract_claims", "check_evidence")
        workflow.add_conditional_edges(
            "check_evidence",
            self._route_evidence,
            {"has_evidence": "advocate", "no_evidence": "insufficient_evidence"},
        )
        workflow.add_edge("advocate", "skeptic")
        workflow.add_edge("skeptic", "judge")
        workflow.add_edge("judge", END)
        workflow.add_edge("insufficient_evidence", END)

        return workflow.compile()

    async def _extract_claims(self, state: VerificationState) -> dict:
        claims = await self.claim_extractor.extract(state["claim_text"])
        return {"atomic_claims": claims}

    async def _check_evidence(self, state: VerificationState) -> dict:
        return {}

    def _route_evidence(self, state: VerificationState) -> str:
        evidence = state.get("evidence", [])
        return "has_evidence" if evidence else "no_evidence"

    async def _run_advocate(self, state: VerificationState) -> dict:
        context = AgentContext(claim_text=state["claim_text"], evidence=state.get("evidence", []))
        response = await self.advocate.defend(context)
        return {"advocate_response": response}

    async def _run_skeptic(self, state: VerificationState) -> dict:
        context = AgentContext(
            claim_text=state["claim_text"],
            evidence=state.get("evidence", []),
            advocate_response=state.get("advocate_response"),
        )
        response = await self.skeptic.challenge(context)
        return {"skeptic_response": response}

    async def _run_judge(self, state: VerificationState) -> dict:
        context = AgentContext(
            claim_text=state["claim_text"],
            evidence=state.get("evidence", []),
            advocate_response=state.get("advocate_response"),
            skeptic_response=state.get("skeptic_response"),
        )
        response = await self.judge.evaluate(context)
        confidence = response.confidence
        return {
            "judge_response": response,
            "overall_verdict": (response.verdict or Verdict.INSUFFICIENT_EVIDENCE).value,
            "overall_confidence": confidence,
            "requires_human_review": confidence < self.human_review_threshold,
        }

    async def _insufficient_evidence(self, state: VerificationState) -> dict:
        from app.domain.enums import AgentRole

        empty = AgentResponse(
            agent=AgentRole.JUDGE,
            reasoning="Insufficient evidence",
            confidence=0.0,
            verdict=Verdict.INSUFFICIENT_EVIDENCE,
        )
        return {
            "judge_response": empty,
            "overall_verdict": Verdict.INSUFFICIENT_EVIDENCE.value,
            "overall_confidence": 0.0,
            "requires_human_review": True,
        }

    async def run(self, claim_text: str, evidence: list[Evidence] | None = None) -> VerificationState:
        initial: VerificationState = {
            "claim_text": claim_text,
            "evidence": evidence or [],
        }
        result = await self.graph.ainvoke(initial)
        return result
