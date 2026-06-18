from pydantic import BaseModel, Field


class PolicyBasis(BaseModel):
    title: str
    source_org: str
    source_url: str
    chunk: str


class PolicyAnswer(BaseModel):
    answer: str
    policy_basis: list[PolicyBasis] = Field(default_factory=list)
    needs_human: bool = False


class PolicyIngestResponse(BaseModel):
    documents: int
    chunks: int

