from pydantic import BaseModel, Field
from typing import Literal


class Evidence(BaseModel):
    title: str
    url: str
    evidence_text: str


class AppResearch(BaseModel):
    app: str
    category: str
    description: str

    auth_methods: list[str]

    access_model: Literal[
        "Self-serve",
        "Gated",
        "Unknown"
    ]

    access_reason: str
    api_surface: str

    mcp_status: Literal[
        "Official",
        "Community",
        "None found",
        "Unknown"
    ]

    buildability: Literal[
        "Buildable today",
        "Partially buildable",
        "Blocked",
        "Needs verification"
    ]

    blocker: str

    # Qwen will return source numbers rather than reproducing
    # the entire evidence objects.
    evidence_refs: list[int] = Field(
        min_length=1
    )

    confidence: Literal[
        "High",
        "Medium",
        "Low"
    ]