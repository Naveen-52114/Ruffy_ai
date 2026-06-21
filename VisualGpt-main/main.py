from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from assistant import VisualAIAssistant

app = FastAPI(title="Visual AI Assistant Backend") or FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assistant = VisualAIAssistant()

class QueryRequest(BaseModel):
    query: str

@app.post("/ask")
async def ask_visual_assistant(request: QueryRequest):
    try:
        result = assistant.generate_response(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Backend running with Gemini API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
