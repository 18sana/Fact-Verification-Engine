from enum import Enum


class VerificationStatus(str, Enum):
    PENDING = "pending"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    PARTIALLY_SUPPORTED = "partially_supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNRESOLVED = "unresolved"


class Verdict(str, Enum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    PARTIALLY_SUPPORTED = "partially_supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AgentRole(str, Enum):
    ADVOCATE = "advocate"
    SKEPTIC = "skeptic"
    JUDGE = "judge"
    EXTRACTOR = "extractor"


class ChallengeType(str, Enum):
    HISTORICAL_CONTRADICTION = "historical_contradiction"
    ALTERNATIVE_INTERPRETATION = "alternative_interpretation"
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"
    MISSING_CONTEXT = "missing_context"
    WEAK_EVIDENCE = "weak_evidence"
    CONFLICTING_SOURCES = "conflicting_sources"
    AMBIGUOUS_WORDING = "ambiguous_wording"
    LOGICAL_INCONSISTENCY = "logical_inconsistency"
    OUTDATED_INFORMATION = "outdated_information"
    UNSUPPORTED_ASSUMPTION = "unsupported_assumption"


class HumanReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class KGEdgeStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    UNRESOLVED = "unresolved"
