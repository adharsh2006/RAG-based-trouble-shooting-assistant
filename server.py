import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from rag.pipeline import RAGPipeline
from rag.history import ChatHistoryDB

app = FastAPI(title="HPC Assistant Gemini Server")

# Initialize DB and Pipeline lazily/globally
db = ChatHistoryDB()
pipeline = None

def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = RAGPipeline()
    return pipeline

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h2>Gemini Frontend is initializing...</h2>")

@app.get("/api/history")
async def get_history():
    return db.list_sessions()

@app.get("/api/history/{session_id}")
async def get_session(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/api/history/new")
async def create_new_session(payload: dict = Body(default={})):
    title = payload.get("title", "New chat")
    session = db.create_session(title=title)
    return session

@app.delete("/api/history/{session_id}")
async def delete_session(session_id: str):
    success = db.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "id": session_id}

class RenamePayload(BaseModel):
    title: str

@app.patch("/api/history/{session_id}")
async def rename_session(session_id: str, payload: RenamePayload):
    success = db.rename_session(session_id, payload.title)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "renamed", "title": payload.title}

class ChatStreamPayload(BaseModel):
    session_id: Optional[str] = None
    question: str

@app.post("/api/chat/stream")
async def chat_stream(payload: ChatStreamPayload):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    session_id = payload.session_id
    if not session_id or not db.get_session(session_id):
        session = db.create_session(title=question[:35])
        session_id = session["id"]

    # Add user message to DB
    db.add_message(session_id, role="user", content=question)

    rag = get_pipeline()

    async def event_generator():
        # Step 1 & 2: Rewrite query and retrieve chunks
        retrieve_res = rag._rewrite_and_retrieve(question)

        # Prepare serializable chunks metadata
        chunks_meta = []
        for doc in retrieve_res["chunks"]:
            chunks_meta.append({
                "source": doc.metadata.get("source", "unknown"),
                "source_type": doc.metadata.get("source_type", ""),
                "content": doc.page_content[:400]
            })

        meta_payload = {
            "rewritten_query": retrieve_res["rewritten_query"],
            "sources": retrieve_res["sources"],
            "chunks": chunks_meta
        }

        # Yield metadata event to client
        yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

        # Stream answer from Gemini
        prompt = rag._build_prompt(retrieve_res["context"], question)
        full_answer = ""

        # Using standard synchronous streaming generator wrapped for SSE
        for chunk in rag.llm.stream(prompt):
            text = chunk.content
            full_answer += text
            data_str = json.dumps({"text": text})
            yield f"event: token\ndata: {data_str}\n\n"
            await asyncio.sleep(0.01)

        # Save assistant message to DB
        db.add_message(
            session_id=session_id,
            role="assistant",
            content=full_answer.strip(),
            metadata=meta_payload
        )

        updated_session = db.get_session(session_id)
        done_payload = {
            "session_id": session_id,
            "title": updated_session["title"] if updated_session else "Chat"
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
