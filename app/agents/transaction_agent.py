from app.agents.base import BaseAgent
from app.schemas.transaction import TransactionFlowResponse


class TransactionAgent(BaseAgent):
    name = "transaction_agent"

    def plan(self, message: str) -> TransactionFlowResponse:
        self.city_guard.assert_request_allowed(message)
        needs_human = any(keyword in message for keyword in ["争议", "产权", "抵押", "查封", "户口", "税费"])
        return TransactionFlowResponse(
            summary="上海二手房买卖可按资格初筛、房源核验、签约、网签、贷款/资金监管、缴税过户、交房结算推进。",
            steps=[
                "确认房源城市为上海并完成房源核验。",
                "收集买卖双方身份、婚姻、产权、委托等材料。",
                "签署居间/买卖相关协议并确认定金、付款节点和违约条款。",
                "按上海流程办理网签、贷款或资金监管、税费申报、过户和交房。",
            ],
            materials=["身份证明", "产权证明", "婚姻状况材料", "委托材料", "付款和贷款相关材料"],
            questions_to_confirm=[
                "买方购房资格和贷款方案是否已由相关机构核验？",
                "房屋是否存在抵押、查封、租赁占用或户口迁出问题？",
                "税费承担、交房日期、附属设施和违约责任是否写清？",
            ],
            needs_human=needs_human,
        )

