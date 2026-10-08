from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from engine import analyze

app = FastAPI(title="VeriForge API", version="0.1.0")

class AnalyzeRequest(BaseModel):
    content: str = Field(min_length=1, max_length=30000)
    input_type: str = "message"
    context: dict = Field(default_factory=dict)

@app.get("/health")
def health():
    return {"status": "ok", "service": "veriforge-api"}

@app.post("/api/v1/analyze")
async def analyze_endpoint(req: AnalyzeRequest):
    try:
        return await analyze(req.content, req.input_type, req.context)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
