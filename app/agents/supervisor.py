import asyncio

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.customer_need_agent import CustomerNeedAgent
from app.agents.document_agent import DocumentAgent
from app.agents.listing_agent import ListingAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.policy_agent import PolicyAgent
from app.agents.rental_recommendation_agent import RentalRecommendationAgent
from app.agents.rental_agent import RentalAgent
from app.agents.repair_agent import RepairAgent
from app.agents.social_insight_agent import SocialInsightAgent
from app.agents.transaction_agent import TransactionAgent
from app.schemas.chat import ChatResponse
from app.schemas.rental import RentalRecommendationRequest
from app.schemas.social_insight import SocialInsightRequest
from app.services.city_guard import CityGuardError

INTENTS = {
    "listing_search",
    "policy_qa",
    "rental_flow",
    "transaction_flow",
    "repair_triage",
    "marketing_copy",
    "document_qa",
    "customer_need_update",
    "rental_map_recommendation",
    "commute_analysis",
    "social_insight_extraction",
    "rental_data_import",
    "smalltalk",
    "human_handoff",
    "out_of_scope",
}


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def handle(self, message: str, *, session: Session | None = None) -> ChatResponse:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.handle_async(message, session=session))
        raise RuntimeError("SupervisorAgent.handle() is synchronous; use handle_async() inside an event loop.")

    async def handle_async(self, message: str, *, session: Session | None = None) -> ChatResponse:
        try:
            self.city_guard.assert_request_allowed(message)
        except CityGuardError as exc:
            return ChatResponse(
                intent="out_of_scope",
                answer=str(exc),
                needs_human=False,
                data={"outside_keywords": exc.result.outside_keywords if exc.result else []},
            )

        compliance = ComplianceAgent(city_guard=self.city_guard, openai_service=self.openai_service).check(
            message
        )
        if not compliance.allowed:
            return ChatResponse(
                intent="human_handoff" if compliance.needs_human else "out_of_scope",
                answer=compliance.reason,
                needs_human=compliance.needs_human,
                data={"compliance": compliance.model_dump()},
            )

        intent = self.detect_intent(message)
        if intent == "listing_search":
            result = ListingAgent(city_guard=self.city_guard, openai_service=self.openai_service).search(
                message, session=session
            )
            return ChatResponse(
                intent=intent,
                answer=f"已按上海范围检索到 {len(result.results)} 套房源。",
                data=result.model_dump(),
            )
        if intent == "rental_map_recommendation":
            rental_request = self._rental_request_from_message(message)
            result = await RentalRecommendationAgent(
                city_guard=self.city_guard,
                openai_service=self.openai_service,
            ).recommend(rental_request, session=session)
            return ChatResponse(
                intent=intent,
                answer=self._summarize_rental_result(result.model_dump()),
                data=result.model_dump(),
            )
        if intent == "commute_analysis":
            rental_request = self._rental_request_from_message(message, allow_demo_data=False)
            result = await RentalRecommendationAgent(
                city_guard=self.city_guard,
                openai_service=self.openai_service,
            ).recommend(rental_request, session=session)
            return ChatResponse(
                intent=intent,
                answer=self._summarize_rental_result(result.model_dump(), commute_only=True),
                data=result.model_dump(),
            )
        if intent == "social_insight_extraction":
            result = SocialInsightAgent(
                city_guard=self.city_guard,
                openai_service=self.openai_service,
            ).extract(SocialInsightRequest(source_type="pasted_text", text=message), session=session)
            return ChatResponse(intent=intent, answer="已抽取租房偏好因素。", data=result.model_dump())
        if intent == "rental_data_import":
            return ChatResponse(
                intent=intent,
                answer="请使用 scripts/import_rental_listings_csv.py 导入真实房源 CSV；导入后推荐才会进入 listing_mode。",
            )
        if intent == "policy_qa":
            result = PolicyAgent(city_guard=self.city_guard, openai_service=self.openai_service).answer(
                message, session=session
            )
            return ChatResponse(
                intent=intent,
                answer=result.answer,
                needs_human=result.needs_human,
                data=result.model_dump(),
            )
        if intent == "repair_triage":
            result = RepairAgent(city_guard=self.city_guard, openai_service=self.openai_service).triage(
                message, session=session
            )
            return ChatResponse(
                intent=intent,
                answer=result.summary,
                needs_human=result.needs_human,
                data=result.model_dump(),
            )
        if intent == "marketing_copy":
            return ChatResponse(
                intent=intent,
                answer="请提供已核验且有效委托的上海房源 listing_id 或 listing facts 后生成文案。",
                needs_human=True,
            )
        if intent == "rental_flow":
            result = RentalAgent(city_guard=self.city_guard, openai_service=self.openai_service).handle(
                message, session=session
            )
            return ChatResponse(
                intent=intent,
                answer=result.get("answer", "已生成上海租赁流程建议。"),
                needs_human=bool(result.get("needs_human", False)),
                data=result,
            )
        if intent == "transaction_flow":
            result = TransactionAgent(city_guard=self.city_guard, openai_service=self.openai_service).plan(
                message
            )
            return ChatResponse(
                intent=intent,
                answer=result.summary,
                needs_human=result.needs_human,
                data=result.model_dump(),
            )
        if intent == "document_qa":
            result = DocumentAgent(city_guard=self.city_guard, openai_service=self.openai_service).answer(
                message, session=session
            )
            return ChatResponse(
                intent=intent,
                answer=result.answer,
                needs_human=result.needs_human,
                data=result.model_dump(),
            )
        if intent == "customer_need_update":
            need = CustomerNeedAgent(city_guard=self.city_guard, openai_service=self.openai_service).extract(
                message
            )
            return ChatResponse(intent=intent, answer="已抽取客户需求。", data=need.model_dump())
        return ChatResponse(intent="smalltalk", answer="我可以协助上海范围内的房源、政策、租赁、交易、维修、营销和文档问答。")

    @staticmethod
    def detect_intent(message: str) -> str:
        if any(keyword in message for keyword in ["导入房源", "导入租房", "房源表", "CSV"]):
            return "rental_data_import"
        if any(keyword in message for keyword in ["小红书截图", "社交平台", "租房笔记", "选房标准"]):
            return "social_insight_extraction"
        if any(keyword in message for keyword in ["算通勤", "通勤分析", "通勤多久", "通勤时间"]):
            return "commute_analysis"
        if any(keyword in message for keyword in ["地图", "租哪里", "高德", "通勤地图"]):
            return "rental_map_recommendation"
        no_demo_terms = ["不允许 demo", "不允许demo", "不要 demo", "不要demo", "不用 demo", "不用demo", "不使用 demo", "不使用demo", "关闭 demo", "关闭demo", "真实房源"]
        area_terms = ["哪些区域", "适合哪些区域", "区域", "板块", "地铁站", "住哪里"]
        if any(keyword in message for keyword in no_demo_terms) and any(keyword in message for keyword in area_terms):
            return "rental_map_recommendation"
        rental_terms = ["租房", "月租", "租金", "想租", "整租", "合租", "一室", "两室", "三室", "区域", "板块"]
        need_terms = ["预算", "上班", "公司", "工作地点", "通勤", "地铁", "推荐", "哪里", "附近", "适合"]
        if any(keyword in message for keyword in rental_terms) and any(keyword in message for keyword in need_terms):
            return "rental_map_recommendation"
        if any(keyword in message for keyword in ["找房", "推荐", "房源", "买房", "租房", "预算"]):
            return "listing_search"
        if any(keyword in message for keyword in ["政策", "备案", "核验码", "规定", "材料"]):
            return "policy_qa"
        if any(keyword in message for keyword in ["出租", "退租", "押金", "群租", "租赁合同"]):
            return "rental_flow"
        if any(keyword in message for keyword in ["交易流程", "过户", "网签", "购房资格", "买卖"]):
            return "transaction_flow"
        if any(keyword in message for keyword in ["维修", "漏水", "燃气", "电路", "消防", "报修"]):
            return "repair_triage"
        if any(keyword in message for keyword in ["文案", "小红书", "朋友圈", "公众号", "视频号", "标题", "带看话术"]):
            return "marketing_copy"
        if any(keyword in message for keyword in ["文档", "合同里", "这份", "附件"]):
            return "document_qa"
        if any(keyword in message for keyword in ["客户", "需求", "画像"]):
            return "customer_need_update"
        if any(keyword in message for keyword in ["人工", "经纪人", "主管"]):
            return "human_handoff"
        return "smalltalk"

    @staticmethod
    def _summarize_rental_result(data: dict, *, commute_only: bool = False) -> str:
        results = data.get("results") or []
        lines = ["已通过高德检索上海小区候选，并按通勤与预算做了排序。"]
        if not results:
            lines.append("暂时没有从高德取得符合条件的上海小区候选；请换一个更具体的上海工作地点或稍后再试。")
            return "\n".join(lines)

        for index, item in enumerate(results[:3], start=1):
            routes = item.get("commute_routes") or []
            best = next(
                (route for route in routes if route.get("route_status") == "ok" and route.get("duration_min") is not None),
                routes[0] if routes else None,
            )
            if best and best.get("route_status") == "ok":
                commute_text = SupervisorAgent._format_commute_text(best)
            elif best:
                commute_text = "路线暂不可用"
            else:
                commute_text = "未计算"
            rent = item.get("rent_monthly")
            rent_text = f"参考租金 {rent} 元/月" if rent is not None else "暂无参考租金"
            if item.get("item_type") == "community":
                data_text = "高德小区候选"
            elif item.get("item_type") == "listing":
                data_text = "真实房源"
            else:
                data_text = "区域候选"
            lines.append(
                f"{index}. {item.get('title')}：{rent_text}，通勤 {commute_text}，{data_text}。"
            )
        if commute_only:
            lines.append("未配置高德密钥或地址无法地理编码时，路线会标记为不可用，不会编造通勤时间。")
        else:
            lines.append("右侧推荐卡片已同步更新。")
        return "\n".join(lines)

    @staticmethod
    def _format_commute_text(route: dict) -> str:
        mode_labels = {
            "transit": "公交地铁",
            "driving": "驾车",
            "walking": "步行",
            "bicycling": "骑行",
            "electrobike": "电动车",
        }
        mode = mode_labels.get(str(route.get("mode")), "通勤")
        try:
            minutes = round(float(route.get("duration_min")))
        except (TypeError, ValueError):
            return f"{mode}路线暂不可用"
        return f"{mode}约 {minutes} 分钟"

    @staticmethod
    def _rental_request_from_message(
        message: str, *, allow_demo_data: bool | None = None
    ) -> RentalRecommendationRequest:
        return RentalRecommendationRequest(
            query=message,
            allow_demo_data=False,
            recommendation_unit="community",
            result_limit=3,
        )
