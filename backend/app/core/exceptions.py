class FVEError(Exception):
    """Base exception for the Fact-Verification Engine."""

    def __init__(self, message: str, code: str = "FVE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InsufficientEvidenceError(FVEError):
    def __init__(self, message: str = "Insufficient evidence to verify claim"):
        super().__init__(message, code="INSUFFICIENT_EVIDENCE")


class ClaimExtractionError(FVEError):
    def __init__(self, message: str):
        super().__init__(message, code="CLAIM_EXTRACTION_ERROR")


class RetrievalError(FVEError):
    def __init__(self, message: str):
        super().__init__(message, code="RETRIEVAL_ERROR")


class KnowledgeGraphError(FVEError):
    def __init__(self, message: str):
        super().__init__(message, code="KNOWLEDGE_GRAPH_ERROR")


class AgentError(FVEError):
    def __init__(self, message: str, agent: str):
        super().__init__(f"[{agent}] {message}", code="AGENT_ERROR")


class TrainingError(FVEError):
    def __init__(self, message: str):
        super().__init__(message, code="TRAINING_ERROR")
