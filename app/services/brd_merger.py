from loguru import logger
from app.core.models import (
    BRDContent,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Risk,
    Likelihood,
    Impact,
)


def merge_brd_chunks(chunks: list[dict]) -> BRDContent:
    """
    Merge multiple AI-extracted BRD JSON chunks into a single validated BRDContent.

    For single-chunk transcripts this is just validation + type coercion.
    For multi-chunk transcripts it deduplicates and re-sequences IDs.
    """
    if not chunks:
        raise ValueError("No BRD chunks to merge")

    merged: dict = {
        "project_name": "Not specified",
        "meeting_date": "Not specified",
        "attendees": [],
        "business_objectives": [],
        "in_scope": [],
        "out_of_scope": [],
        "functional_requirements": [],
        "non_functional_requirements": [],
        "assumptions": [],
        "constraints": [],
        "risks": [],
    }

    for chunk in chunks:
        # Take first non-placeholder project name / date found
        if merged["project_name"] == "Not specified" and chunk.get("project_name", "Not specified") != "Not specified":
            merged["project_name"] = chunk["project_name"]

        if merged["meeting_date"] == "Not specified" and chunk.get("meeting_date", "Not specified") != "Not specified":
            merged["meeting_date"] = chunk["meeting_date"]

        # Merge list fields — deduplicate by normalised lowercase string
        for list_field in ("attendees", "business_objectives", "in_scope",
                           "out_of_scope", "assumptions", "constraints"):
            existing_normalised = {_normalise(x) for x in merged[list_field]}
            for item in chunk.get(list_field, []):
                if _normalise(item) not in existing_normalised:
                    merged[list_field].append(item)
                    existing_normalised.add(_normalise(item))

        # Merge requirements — deduplicate by normalised description
        for req_field in ("functional_requirements", "non_functional_requirements", "risks"):
            existing_normalised = {_normalise(r.get("description", "")) for r in merged[req_field]}
            for item in chunk.get(req_field, []):
                if _normalise(item.get("description", "")) not in existing_normalised:
                    merged[req_field].append(item)
                    existing_normalised.add(_normalise(item.get("description", "")))

    # Re-sequence IDs cleanly after merge
    merged["functional_requirements"] = _resequence(
        merged["functional_requirements"], "FR"
    )
    merged["non_functional_requirements"] = _resequence(
        merged["non_functional_requirements"], "NFR"
    )
    merged["risks"] = _resequence(merged["risks"], "RISK")

    logger.info(
        f"BRD merge complete | project='{merged['project_name']}' | "
        f"FR={len(merged['functional_requirements'])} | "
        f"NFR={len(merged['non_functional_requirements'])} | "
        f"Risks={len(merged['risks'])}"
    )

    return _validate(merged)


def _resequence(items: list[dict], prefix: str) -> list[dict]:
    """Assign clean sequential IDs: FR-001, FR-002, etc."""
    return [{**item, "id": f"{prefix}-{i+1:03d}"} for i, item in enumerate(items)]


def _normalise(text: str) -> str:
    """Lowercase + strip for deduplication comparison."""
    return text.lower().strip()


def _validate(data: dict) -> BRDContent:
    """
    Coerce raw dict to typed BRDContent.
    Handles cases where the model returns slightly wrong enum values.
    """
    _LIKELIHOOD_MAP = {v.lower(): v for v in ("Low", "Medium", "High")}
    _IMPACT_MAP = {v.lower(): v for v in ("Low", "Medium", "High")}
    _PRIORITY_MAP = {v.lower(): v for v in ("Low", "Medium", "High")}

    # Coerce FRs
    frs = []
    for r in data.get("functional_requirements", []):
        frs.append(FunctionalRequirement(
            id=r.get("id", "FR-000"),
            description=r.get("description", ""),
            priority=_PRIORITY_MAP.get(str(r.get("priority", "Medium")).lower(), "Medium"),
        ))

    # Coerce NFRs
    nfrs = []
    for r in data.get("non_functional_requirements", []):
        nfrs.append(NonFunctionalRequirement(
            id=r.get("id", "NFR-000"),
            category=r.get("category", "General"),
            description=r.get("description", ""),
        ))

    # Coerce Risks
    risks = []
    for r in data.get("risks", []):
        risks.append(Risk(
            id=r.get("id", "RISK-000"),
            description=r.get("description", ""),
            likelihood=Likelihood(_LIKELIHOOD_MAP.get(str(r.get("likelihood", "Medium")).lower(), "Medium")),
            impact=Impact(_IMPACT_MAP.get(str(r.get("impact", "Medium")).lower(), "Medium")),
            mitigation=r.get("mitigation", "Not discussed"),
        ))

    return BRDContent(
        project_name=data.get("project_name", "Not specified"),
        meeting_date=data.get("meeting_date", "Not specified"),
        attendees=data.get("attendees", []),
        business_objectives=data.get("business_objectives", []),
        in_scope=data.get("in_scope", []),
        out_of_scope=data.get("out_of_scope", []),
        functional_requirements=frs,
        non_functional_requirements=nfrs,
        assumptions=data.get("assumptions", []),
        constraints=data.get("constraints", []),
        risks=risks,
    )
