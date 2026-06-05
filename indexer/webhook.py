from fastapi import FastAPI, Request

app = FastAPI(title="Webhook Receiver")


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, str]:
    await request.body()
    return {"status": "received"}
