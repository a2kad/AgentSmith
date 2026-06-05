from fastapi import FastAPI, Request, BackgroundTasks
import os
import json
import hmac
import hashlib
from memory.codebase_indexer import CodebaseIndexer
from langchain_openai import OpenAIEmbeddings

app = FastAPI(title="Webhook Receiver")
embedder = OpenAIEmbeddings(model="text-embedding-3-large")
indexer = CodebaseIndexer(
    qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    embedder=embedder
)

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    
    if not verify_github_signature(payload, signature, secret):
        return {"status": "unauthorized"}
    
    event = json.loads(payload)
    if event.get("action") == "opened" or event.get("action") == "synchronize":
        files_changed = {}
        for file in event.get("pull_request", {}).get("changed_files", []):
            files_changed[file["filename"]] = file.get("patch", "")
        
        commit_sha = event["pull_request"]["head"]["sha"]
        background_tasks.add_task(indexer.index_commit, files_changed, commit_sha)
    
    return {"status": "received"}

@app.get("/health")
async def health():
    return {"status": "ready"}
