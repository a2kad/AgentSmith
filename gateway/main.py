from approval_api import app


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
