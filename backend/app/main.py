from fastapi import FastAPI

app = FastAPI(title="羽毛球约球助手")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
