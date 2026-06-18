from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.routes import agent, chat, commute, documents, geo, health, insights, listings, map, marketing, policies, rental, repair
from app.config import get_settings
from app.services.city_guard import CityGuardError

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/agent")


@app.exception_handler(CityGuardError)
async def city_guard_exception_handler(request: Request, exc: CityGuardError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc), "needs_human": False})


app.include_router(health.router)
app.include_router(agent.router)
app.include_router(chat.router)
app.include_router(listings.router)
app.include_router(policies.router)
app.include_router(documents.router)
app.include_router(repair.router)
app.include_router(marketing.router)
app.include_router(geo.router)
app.include_router(commute.router)
app.include_router(rental.router)
app.include_router(map.router)
app.include_router(insights.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
