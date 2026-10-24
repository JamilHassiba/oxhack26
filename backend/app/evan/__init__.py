"""Evan-owned API services. Shared app/db/orchestrator files stay with their owners."""


def register_routes(app):
    """Call once from Alex's create_app() after the shared DB lifespan is installed."""
    from app.routers import agents, calendar, tasks

    for router in (agents.router, tasks.router, calendar.router):
        app.include_router(router)
