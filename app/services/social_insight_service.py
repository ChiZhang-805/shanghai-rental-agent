from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.social_insight import SocialInsight
from app.schemas.rental import RentalPreferenceWeights
from app.schemas.social_insight import SocialInsightRequest, SocialInsightResponse
from app.services.image_service import ImageService
from app.services.openai_service import OpenAIService


class SocialInsightService:
    def __init__(self, openai_service: OpenAIService | None = None) -> None:
        self.openai_service = openai_service or OpenAIService()

    def extract(
        self,
        request: SocialInsightRequest,
        *,
        session: Session | None = None,
    ) -> SocialInsightResponse:
        fallback = self._fallback(request)
        prompt = (
            "你是上海租房偏好分析 Agent。把用户粘贴或上传的租房观点转成可执行评分因素。"
            "社交平台观点只能作为偏好参考，不能当事实；不要推荐具体房源。"
            f"\n用户上下文：{request.user_context or ''}\n文本：{request.text or ''}"
        )
        if request.source_type == "uploaded_image" and request.image_path:
            image_path = ImageService.resolve_upload_image_path(
                request.image_path, self.openai_service.settings.upload_dir
            )
            if image_path is None:
                fallback.caution_notes.append("图片路径不在允许上传目录，已忽略图片。")
                data = fallback.model_dump()
            else:
                image_data_url = ImageService.file_to_data_url(image_path)
                data = self.openai_service.analyze_image_json(
                    prompt=prompt,
                    image_data_url=image_data_url,
                    schema_model=SocialInsightResponse,
                    schema_name="social_insight",
                    fallback=fallback.model_dump(),
                )
        else:
            data = self.openai_service.generate_json(
                prompt=prompt,
                schema_model=SocialInsightResponse,
                schema_name="social_insight",
                fallback=fallback.model_dump(),
            )
        response = SocialInsightResponse.model_validate(data)
        if session is not None:
            try:
                session.add(
                    SocialInsight(
                        source_type=request.source_type,
                        source_note=request.user_context,
                        extracted_text=response.extracted_text,
                        extracted_criteria=[criterion.model_dump() for criterion in response.criteria],
                        suggested_weights=response.suggested_weights.model_dump(),
                        caution_notes=response.caution_notes,
                    )
                )
                session.commit()
            except Exception:
                session.rollback()
        return response

    @staticmethod
    def _fallback(request: SocialInsightRequest) -> SocialInsightResponse:
        text = request.text or ""
        caution = ["社交平台观点只能作为偏好参考，不能替代真实房源核验"]
        criteria = []
        weights = {}
        if any(keyword in text for keyword in ["通勤", "上班", "公司"]):
            criteria.append({"name": "通勤时间", "importance": "high", "scoring_hint": "优先控制在用户阈值以内"})
            weights["commute"] = 0.4
        if any(keyword in text for keyword in ["地铁", "站"]):
            criteria.append({"name": "地铁便利", "importance": "medium", "scoring_hint": "距离地铁800米以内更优"})
            weights["transit_access"] = 0.18
        if any(keyword in text for keyword in ["预算", "租金", "押金"]):
            criteria.append({"name": "预算压力", "importance": "high", "scoring_hint": "月租和押付压力都需要关注"})
            weights["budget"] = 0.28
        payload = SocialInsightResponse(extracted_text=text, criteria=criteria, caution_notes=caution)
        if weights:
            base = payload.suggested_weights.model_dump()
            base.update(weights)
            payload.suggested_weights = RentalPreferenceWeights.model_validate(base)
        return payload
