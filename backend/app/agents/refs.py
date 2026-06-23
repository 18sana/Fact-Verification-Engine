import re
from typing import Any, Optional

from app.domain.models import Evidence

_INDEX_RE = re.compile(r"^\[?(\d+)\]?$")


def _resolve_ref(item: Any, evidence: Optional[list[Evidence]]) -> Optional[str]:
    if item is None:
        return None
    s = str(item).strip()
    if not s:
        return None

    if _INDEX_RE.match(s) and evidence:
        idx = int(_INDEX_RE.match(s).group(1)) - 1  # type: ignore[union-attr]
        if 0 <= idx < len(evidence):
            return str(evidence[idx].id)

    # Already a UUID or opaque string id
    return s


def normalize_evidence_refs(values: Any, evidence: Optional[list[Evidence]] = None) -> list[str]:
    """Coerce LLM refs (ints like 1,2 or UUID strings) to string evidence ids."""
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]
    refs: list[str] = []
    for item in values:
        resolved = _resolve_ref(item, evidence)
        if resolved:
            refs.append(resolved)
    return refs


def normalize_challenge_refs(challenges: list[dict], evidence: Optional[list[Evidence]] = None) -> list[dict]:
    normalized = []
    for ch in challenges:
        ch = dict(ch)
        ch["evidence_refs"] = normalize_evidence_refs(ch.get("evidence_refs", []), evidence)
        normalized.append(ch)
    return normalized
