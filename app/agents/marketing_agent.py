from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.compliance_agent import ComplianceAgent
from app.models.listing import Listing
from app.schemas.marketing import MarketingGenerateResponse


class MarketingAgent(BaseAgent):
    name = "marketing_agent"

    def __init__(self, *, compliance_agent: ComplianceAgent | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.compliance_agent = compliance_agent or ComplianceAgent(
            city_guard=self.city_guard, openai_service=self.openai_service
        )

    def generate(
        self,
        *,
        listing: dict[str, Any] | None = None,
        listing_id: int | None = None,
        channel: str = "朋友圈",
        tone: str = "专业、真实、克制",
        session: Session | None = None,
    ) -> MarketingGenerateResponse:
        listing_data = listing or self._load_listing(session, listing_id)
        if listing_data is None:
            return MarketingGenerateResponse(
                allowed=False,
                channel=channel,
                refusal_reason="未找到房源，不能生成对外营销文案。",
                risk_flags=["missing_listing"],
            )
        try:
            self.city_guard.validate_listing_rows([listing_data])
        except Exception as exc:
            return MarketingGenerateResponse(
                allowed=False,
                channel=channel,
                refusal_reason=str(exc),
                risk_flags=["outside_shanghai_listing"],
            )
        if listing_data.get("verification_status") != "verified":
            return MarketingGenerateResponse(
                allowed=False,
                channel=channel,
                refusal_reason="房源未核验通过，不能生成对外营销文案。",
                risk_flags=["unverified_listing_marketing"],
            )
        if listing_data.get("entrusted_status") != "active":
            return MarketingGenerateResponse(
                allowed=False,
                channel=channel,
                refusal_reason="房源委托状态不是 active，不能生成对外营销文案。",
                risk_flags=["inactive_entrustment_marketing"],
            )

        draft = self._build_copy(listing_data, channel, tone)
        compliance = self.compliance_agent.check(f"生成{channel}文案：{draft}", listing=listing_data)
        if not compliance.allowed:
            return MarketingGenerateResponse(
                allowed=False,
                channel=channel,
                refusal_reason=compliance.reason,
                risk_flags=compliance.violations,
            )
        return MarketingGenerateResponse(
            allowed=True,
            channel=channel,
            copy=draft,
            requires_human_review=True,
            risk_flags=[],
        )

    @staticmethod
    def _build_copy(listing: dict[str, Any], channel: str, tone: str) -> str:
        price = listing.get("sale_price_total") or listing.get("rent_price_monthly")
        price_label = "总价" if listing.get("purpose") == "sale" else "月租"
        parts = [
            f"【{listing.get('district')}｜{listing.get('community_name')}】",
            f"{listing.get('title')}",
            f"{listing.get('area_sqm')}平，{listing.get('rooms') or '?'}房，{price_label}{price}元。",
            f"房源核验状态：{listing.get('verification_status')}；委托状态：{listing.get('entrusted_status')}。",
            f"适合{channel}发布，语气：{tone}。",
            "信息以现场带看、业主委托及官方核验结果为准，不作入学、落户、贷款、涨价或收益承诺。",
        ]
        return "\n".join(parts)

    @staticmethod
    def _load_listing(session: Session | None, listing_id: int | None) -> dict[str, Any] | None:
        if session is None or listing_id is None:
            return None
        listing = session.scalar(select(Listing).where(Listing.id == listing_id))
        if listing is None:
            return None
        return {
            "id": listing.id,
            "listing_code": listing.listing_code,
            "city": listing.city,
            "district": listing.district,
            "community_name": listing.community_name,
            "title": listing.title,
            "purpose": listing.purpose,
            "rooms": listing.rooms,
            "area_sqm": listing.area_sqm,
            "sale_price_total": listing.sale_price_total,
            "rent_price_monthly": listing.rent_price_monthly,
            "verification_status": listing.verification_status,
            "entrusted_status": listing.entrusted_status,
            "listing_status": listing.listing_status,
        }

