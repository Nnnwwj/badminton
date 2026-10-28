from fastapi import FastAPI

from app.api.profile import router as profile_router


app = FastAPI(title="羽毛球约球助手")
app.include_router(profile_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
