from app.agents.policy_agent import PolicyAgent
from app.services.policy_service import PolicyChunkRecord


def test_policy_agent_does_not_answer_without_source() -> None:
    response = PolicyAgent().answer("上海租赁备案需要什么材料？", chunks=[])
    assert response.policy_basis == []
    assert "本地政策库没有检索到" in response.answer


def test_policy_agent_returns_policy_basis_when_source_exists() -> None:
    chunks = [
        PolicyChunkRecord(
            title="上海租赁备案材料摘要",
            source_org="上海市住房租赁公共服务平台",
            source_url="https://example.gov.cn/policy",
            doc_type="rental",
            content="上海租赁备案需要核对租赁合同、身份材料、房屋权属或合法来源材料。",
        )
    ]
    response = PolicyAgent().answer("上海租赁备案需要什么材料？", chunks=chunks)
    assert response.policy_basis
    assert response.policy_basis[0].title == "上海租赁备案材料摘要"

