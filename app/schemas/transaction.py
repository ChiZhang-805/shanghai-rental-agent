from pydantic import BaseModel, Field


class TransactionFlowResponse(BaseModel):
    summary: str
    steps: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    questions_to_confirm: list[str] = Field(default_factory=list)
    needs_human: bool = False
    disclaimer: str = "仅供上海交易流程初筛参考，最终以主管部门、银行和人工审核为准。"

