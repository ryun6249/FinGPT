from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.openbb_agent import router as openbb_agent_router
from app.api.routers.backtest import router as backtest_router
from app.api.routers.ai_portfolio import router as ai_portfolio_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.data import router as data_router
from app.api.routers.forecast import router as forecast_router
from app.api.routers.macro import router as macro_router
from app.api.routers.portfolio import router as portfolio_router
from app.api.routers.quantamental import router as quantamental_router
from app.api.routers.quant_lab import router as quant_lab_router
from app.api.routers.research import router as research_router
from app.api.routers.system import router as system_router
from app.api.routers.watchlist import router as watchlist_router
from core.config.settings import load_settings
from core.utils.logger import get_logger
from pipelines.data_mart.scheduler import get_scheduler as get_data_mart_scheduler
from pipelines.watchlist.scheduler import get_scheduler as get_watchlist_scheduler


logger = get_logger("api.server")
_settings = load_settings()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "app" / "web"


class UiStaticFiles(StaticFiles):
    """Serve the static UI while allowing direct links to client-side routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or Path(path).suffix:
                raise
            return await super().get_response("index.html", scope)


async def _start_watchlist_scheduler() -> None:
    """Spin up the in-process watchlist scheduler once the event loop is ready."""

    try:
        await get_watchlist_scheduler().start()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to start watchlist scheduler: {exc}")


async def _start_data_mart_scheduler() -> None:
    """Start structured data refresh jobs without blocking API startup."""

    try:
        await get_data_mart_scheduler().start()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to start data mart scheduler: {exc}")


async def _stop_watchlist_scheduler() -> None:
    try:
        await get_watchlist_scheduler().stop()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to stop watchlist scheduler cleanly: {exc}")


async def _stop_data_mart_scheduler() -> None:
    try:
        await get_data_mart_scheduler().stop()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to stop data mart scheduler cleanly: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _start_watchlist_scheduler()
    await _start_data_mart_scheduler()
    try:
        yield
    finally:
        await _stop_data_mart_scheduler()
        await _stop_watchlist_scheduler()


app = FastAPI(
    title="FinGPT Local Research Assistant",
    description="Local, privacy-preserving financial research API + Web UI.",
    version="1.1.0",
    lifespan=lifespan,
)

_raw_origins = (_settings.web_cors_origins or "").strip()
_cors_origins = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()] or [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
if bool(getattr(_settings, "openbb_agent_enabled", False)):
    for origin in str(getattr(_settings, "openbb_agent_allow_origins", "") or "").split(","):
        origin = origin.strip()
        if origin and origin not in _cors_origins:
            _cors_origins.append(origin)
_allow_any = _cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=None if not _allow_any else ".*",
    allow_credentials=not _allow_any,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(openbb_agent_router)
app.include_router(system_router)
app.include_router(research_router)
app.include_router(data_router)
app.include_router(dashboard_router)
app.include_router(backtest_router)
app.include_router(portfolio_router)
app.include_router(ai_portfolio_router, prefix="/api/v1/ai-portfolio")
app.include_router(ai_portfolio_router, prefix="/api/ai-portfolio")
app.include_router(watchlist_router)
app.include_router(macro_router, prefix="/api/v1/macro")
app.include_router(macro_router, prefix="/api/macro")
app.include_router(quant_lab_router)
app.include_router(forecast_router, prefix="/api/v1/forecast")
app.include_router(forecast_router, prefix="/api/forecast")
app.include_router(quantamental_router, prefix="/api/v1/quantamental")
app.include_router(quantamental_router, prefix="/api/quantamental")

if WEB_DIR.exists():
    app.mount("/ui", UiStaticFiles(directory=str(WEB_DIR), html=True), name="web")

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/ui/")
else:  # pragma: no cover - only triggered if web assets are removed
    logger.warning(f"Web UI directory not found at {WEB_DIR}; serving API only.")
