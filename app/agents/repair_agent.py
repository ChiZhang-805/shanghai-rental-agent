from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.repair import RepairTicket
from app.schemas.repair import RepairTriageResponse
from app.services.image_service import ImageService


class RepairAgent(BaseAgent):
    name = "repair_agent"

    def triage(
        self,
        description: str,
        *,
        image_path: str | None = None,
        session: Session | None = None,
    ) -> RepairTriageResponse:
        self.city_guard.assert_request_allowed(description)
        response = self._rule_triage(description)
        safe_image_path = (
            ImageService.resolve_upload_image_path(image_path, self.openai_service.settings.upload_dir)
            if image_path
            else None
        )
        if safe_image_path is not None and self.openai_service.is_configured:
            image_data_url = ImageService.file_to_data_url(safe_image_path)
            prompt = (
                "你是上海房屋维修分诊 Agent。根据图片和文字输出维修结构化 JSON。"
                "燃气、电路、消防、严重漏水必须 needs_human=true。文字描述："
                f"{description}"
            )
            data = self.openai_service.analyze_image_json(
                prompt=prompt,
                image_data_url=image_data_url,
                schema_model=RepairTriageResponse,
                schema_name="repair_triage",
                fallback=response.model_dump(),
            )
            response = RepairTriageResponse.model_validate(data)

        if session is not None:
            ticket = RepairTicket(
                issue_type=response.issue_type,
                severity=response.severity,
                summary=response.summary,
                ticket_title=response.ticket_title,
                ticket_description=response.ticket_description,
                needs_human=response.needs_human,
                risk_flags=response.risk_flags,
                source_image_path=str(safe_image_path) if safe_image_path is not None else None,
            )
            try:
                session.add(ticket)
                session.commit()
                session.refresh(ticket)
                response.ticket_id = ticket.id
            except Exception:
                session.rollback()
        return response

    @staticmethod
    def _rule_triage(description: str) -> RepairTriageResponse:
        text = description
        if any(keyword in text for keyword in ["燃气", "煤气", "天然气", "异味"]):
            return RepairTriageResponse(
                issue_type="gas",
                severity="emergency",
                summary="疑似燃气安全风险。",
                immediate_actions=[
                    "立即开窗通风，人员远离气味明显区域。",
                    "不要开关电器、不要点火、不要使用明火。",
                    "尽快联系物业、燃气公司或应急人员现场处理。",
                ],
                questions_to_ask=["异味从什么时候开始？", "阀门是否已关闭？", "现场是否有人头晕不适？"],
                ticket_title="燃气异味紧急工单",
                ticket_description=description,
                needs_human=True,
                risk_flags=["safety_risk", "gas"],
            )
        if any(keyword in text for keyword in ["漏电", "电路", "跳闸", "冒烟", "电火花"]):
            return RepairTriageResponse(
                issue_type="electrical",
                severity="emergency",
                summary="疑似电路安全风险。",
                immediate_actions=["远离故障电器和潮湿区域。", "在安全前提下关闭对应电源。", "联系电工或物业现场处理。"],
                questions_to_ask=["是否有冒烟或焦糊味？", "是否反复跳闸？"],
                ticket_title="电路安全紧急工单",
                ticket_description=description,
                needs_human=True,
                risk_flags=["safety_risk", "electrical"],
            )
        if any(keyword in text for keyword in ["消防", "着火", "火灾", "明火"]):
            return RepairTriageResponse(
                issue_type="fire",
                severity="emergency",
                summary="疑似消防安全风险。",
                immediate_actions=["立即撤离到安全区域。", "必要时拨打 119。", "通知物业和相关责任人。"],
                questions_to_ask=["是否仍有明火？", "是否有人受伤？"],
                ticket_title="消防安全紧急工单",
                ticket_description=description,
                needs_human=True,
                risk_flags=["safety_risk", "fire"],
            )
        if any(keyword in text for keyword in ["严重漏水", "水漫", "爆管"]):
            return RepairTriageResponse(
                issue_type="plumbing",
                severity="urgent",
                summary="疑似严重漏水，需要尽快现场处理。",
                immediate_actions=["关闭就近水阀。", "避开涉水电器和插座。", "联系物业或维修人员。"],
                questions_to_ask=["漏水点在哪里？", "是否影响楼下或公共区域？"],
                ticket_title="严重漏水维修工单",
                ticket_description=description,
                needs_human=True,
                risk_flags=["safety_risk", "water_leak"],
            )
        if "漏水" in text:
            return RepairTriageResponse(
                issue_type="plumbing",
                severity="normal",
                summary="普通漏水报修。",
                immediate_actions=["拍照记录漏水位置。", "清理附近物品，避免扩大损失。"],
                questions_to_ask=["漏水频率如何？", "是否能看到明确漏水点？"],
                ticket_title="漏水维修工单",
                ticket_description=description,
                needs_human=False,
                risk_flags=["water_leak"],
            )
        return RepairTriageResponse(
            issue_type="general",
            severity="normal",
            summary="普通维修问题。",
            immediate_actions=["记录问题位置和发生时间。", "补充照片或视频便于派单。"],
            questions_to_ask=["具体房间和位置在哪里？", "问题出现多久了？"],
            ticket_title="普通维修工单",
            ticket_description=description,
            needs_human=False,
            risk_flags=[],
        )
