from app.agents.customer_need_agent import CustomerNeedAgent


def test_extract_budget_800_wan_to_yuan() -> None:
    need = CustomerNeedAgent().extract("客户想买浦东三房，预算800万以内")
    assert need.city == "上海"
    assert need.purpose == "sale"
    assert need.budget_max == 8_000_000
    assert need.rooms_min == 3
    assert "浦东" in need.districts

