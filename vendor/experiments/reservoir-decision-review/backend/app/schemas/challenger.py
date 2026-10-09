from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.validators import assert_bare_source_ids


class ChallengerVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ChallengerFinding(BaseModel):
    finding_challenged: str
    verdict: ChallengerVerdict
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    qualification: str | None = None
    missing_information: str | None = None

    _validate_supporting = field_validator("supporting_evidence")(assert_bare_source_ids)
    _validate_contradictory = field_validator("contradictory_evidence")(assert_bare_source_ids)


class EvidenceChallengerOutput(BaseModel):
    proposed_decision: str
    findings: list[ChallengerFinding] = Field(default_factory=list)

    def all_cited_source_ids(self) -> set[str]:
        ids: set[str] = set()
        for f in self.findings:
            ids.update(f.supporting_evidence)
            ids.update(f.contradictory_evidence)
        return ids
