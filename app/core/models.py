from pydantic import BaseModel, Field
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class Likelihood(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Impact(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# ── BRD Section Models ─────────────────────────────────────────────────────────

class FunctionalRequirement(BaseModel):
    id: str = Field(description="e.g. FR-001")
    description: str
    priority: str = Field(default="Medium", description="High | Medium | Low")


class NonFunctionalRequirement(BaseModel):
    id: str = Field(description="e.g. NFR-001")
    category: str = Field(description="e.g. Performance, Security, Scalability")
    description: str


class Risk(BaseModel):
    id: str = Field(description="e.g. RISK-001")
    description: str
    likelihood: Likelihood
    impact: Impact
    mitigation: str


class BRDContent(BaseModel):
    """
    Structured BRD content extracted from transcript by AI.
    Every field maps directly to a section in the company template.
    """
    project_name: str = Field(description="Inferred project name from transcript")
    meeting_date: str = Field(description="Date of meeting, inferred or 'Not specified'")
    attendees: list[str] = Field(default_factory=list, description="Names/roles identified in transcript")

    business_objectives: list[str] = Field(
        description="List of business objectives discussed"
    )
    in_scope: list[str] = Field(
        description="Items explicitly identified as in scope"
    )
    out_of_scope: list[str] = Field(
        description="Items explicitly identified as out of scope"
    )
    functional_requirements: list[FunctionalRequirement] = Field(
        description="Numbered functional requirements"
    )
    non_functional_requirements: list[NonFunctionalRequirement] = Field(
        description="Numbered non-functional requirements"
    )
    assumptions: list[str] = Field(
        description="Assumptions stated or implied during the meeting"
    )
    constraints: list[str] = Field(
        description="Hard constraints: budget, time, technology, regulatory"
    )
    risks: list[Risk] = Field(
        description="Identified risks with likelihood, impact, and mitigation"
    )


# ── API Request / Response Models ──────────────────────────────────────────────

class BRDResponse(BaseModel):
    """Returned to Power Automate after successful BRD generation."""
    success: bool
    job_id: str
    project_name: str
    filename: str = Field(description="Suggested filename for the output .docx")
    docx_base64: str = Field(description="Base64-encoded .docx for Power Automate to decode and attach")
    sections_extracted: dict[str, int] = Field(
        description="Count of items extracted per section — useful for validation"
    )


class ErrorResponse(BaseModel):
    success: bool = False
    job_id: str
    error: str
    detail: str | None = None
