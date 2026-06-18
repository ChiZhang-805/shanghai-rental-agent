from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.customer_need_agent import CustomerNeedAgent
from app.schemas.listings import ListingSearchRequest, ListingSearchResponse
from app.services.listing_service import ListingService


class ListingAgent(BaseAgent):
    name = "listing_agent"

    def __init__(self, *, listing_service: ListingService | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.listing_service = listing_service or ListingService(self.city_guard)
        self.need_agent = CustomerNeedAgent(city_guard=self.city_guard, openai_service=self.openai_service)

    def search(
        self,
        request: ListingSearchRequest | str,
        *,
        session: Session | None = None,
        listing_rows: list[object] | None = None,
    ) -> ListingSearchResponse:
        if isinstance(request, str):
            need = self.need_agent.extract(request)
            search_request = ListingSearchRequest(
                query=request,
                purpose=need.purpose,
                districts=need.districts,
                budget_min=need.budget_min,
                budget_max=need.budget_max,
                rooms_min=need.rooms_min,
                rooms_max=need.rooms_max,
            )
        else:
            search_request = request
        return self.listing_service.search(search_request, session=session, listing_rows=listing_rows)

