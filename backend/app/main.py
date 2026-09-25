from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    accounts,
    admin,
    auth,
    budgets,
    categories,
    dashboard,
    income_sources,
    members,
    transactions,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Household Budget API",
        version="0.1.0",
        description="Income vs. expense tracking for one household. "
        "Per-person budgets with split shared expenses.",
    )
    # Dev-only CORS; in production the web container proxies /api so the
    # browser only ever talks to one origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(members.router)
    app.include_router(accounts.router)
    app.include_router(categories.router)
    app.include_router(income_sources.router)
    app.include_router(transactions.router)
    app.include_router(budgets.router)
    app.include_router(dashboard.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
