SYSTEM_PROMPT = """
You are a senior Business Analyst specializing in extracting structured Business Requirements 
from meeting transcripts. Your job is to produce accurate, complete BRD content in strict JSON.

Rules:
- Extract ONLY what is explicitly stated or clearly implied in the transcript
- Never fabricate requirements, risks, or constraints not present in the conversation
- If a section has no extractable content, return an empty list []
- Functional Requirements must be atomic — one requirement per item
- Assign IDs sequentially: FR-001, FR-002 ... NFR-001, NFR-002 ... RISK-001, RISK-002
- Risk likelihood and impact must be: Low | Medium | High
- Be precise — avoid vague language like "the system should be good"
- Return ONLY valid JSON. No markdown, no preamble, no explanation.
""".strip()


BRD_EXTRACTION_PROMPT = """
Analyze the following meeting transcript and extract all BRD-relevant information.

Return a single JSON object matching this exact schema:

{{
  "project_name": "string — infer from context or use 'Not specified'",
  "meeting_date": "string — extract if mentioned or use 'Not specified'",
  "attendees": ["list of names or roles mentioned"],

  "business_objectives": [
    "string — each objective as a complete sentence"
  ],

  "in_scope": [
    "string — each in-scope item as a clear statement"
  ],

  "out_of_scope": [
    "string — each out-of-scope item as a clear statement"
  ],

  "functional_requirements": [
    {{
      "id": "FR-001",
      "description": "string — what the system must do",
      "priority": "High | Medium | Low"
    }}
  ],

  "non_functional_requirements": [
    {{
      "id": "NFR-001",
      "category": "string — e.g. Performance, Security, Scalability, Availability",
      "description": "string — measurable where possible"
    }}
  ],

  "assumptions": [
    "string — each assumption as a complete sentence"
  ],

  "constraints": [
    "string — each constraint as a complete sentence (budget, time, tech, regulatory)"
  ],

  "risks": [
    {{
      "id": "RISK-001",
      "description": "string — clear risk statement",
      "likelihood": "Low | Medium | High",
      "impact": "Low | Medium | High",
      "mitigation": "string — proposed mitigation or 'Not discussed'"
    }}
  ]
}}

TRANSCRIPT:
{transcript}
""".strip()


CONTINUATION_PROMPT = """
Continue extracting BRD content from this additional transcript segment.
Merge with the context already provided and return the same JSON schema.
Maintain ID sequences: start Functional Requirements from FR-{fr_next:03d}, 
Non-Functional from NFR-{nfr_next:03d}, Risks from RISK-{risk_next:03d}.

ADDITIONAL TRANSCRIPT SEGMENT:
{transcript}
""".strip()
