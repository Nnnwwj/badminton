from fastapi import FastAPI

from app.api.feedback import admin_router, router as feedback_router
from app.api.profile import router as profile_router
from app.api.sessions import router as sessions_router


app = FastAPI(title="羽毛球约球助手")
app.include_router(profile_router)
app.include_router(sessions_router)
app.include_router(feedback_router)
app.include_router(admin_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
