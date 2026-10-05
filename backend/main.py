import os
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import rag

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Almaari API",
    description="Backend API for Almaari - AI-powered document archive portal.",
    version="1.0.0"
)

# Enable CORS for local Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class AskRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {
        "portal": "Almaari",
        "tagline": "Apni files se poochho. (Ask your files anything.)",
        "status": "online"
    }


@app.post("/login")
def login(creds: LoginRequest):
    """Simple username/password login stored in SQLite."""
    user = db.authenticate_user(creds.username.strip(), creds.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password. The cupboard remains locked."
        )

    return {
        "success": True,
        "username": user["username"],
        "token": f"almaari_token_{user['username']}_{uuid.uuid4().hex[:8]}"
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts PDF or TXT file, saves it to uploads/,
    extracts text, splits into chunks (~500 words),
    and stores embeddings in ChromaDB.
    """
    original_name = file.filename
    if not original_name:
        raise HTTPException(status_code=400, detail="No file name provided.")

    ext = Path(original_name).suffix.lower()
    if ext not in [".pdf", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Only .pdf and .txt files can be kept in Almaari."
        )

    # Generate a safe local filename to avoid clashes
    safe_filename = f"{uuid.uuid4().hex[:8]}_{original_name}"
    save_path = UPLOADS_DIR / safe_filename

    # Save uploaded file
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    file_size = save_path.stat().st_size

    # Index into ChromaDB
    try:
        chunk_count = rag.index_document(str(save_path), doc_name=original_name)
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to process and index document: {str(e)}")

    # Record in SQLite
    doc_id = db.add_document(
        filename=safe_filename,
        original_name=original_name,
        file_size=file_size,
        chunk_count=chunk_count
    )

    return {
        "id": doc_id,
        "filename": safe_filename,
        "original_name": original_name,
        "file_size": file_size,
        "chunk_count": chunk_count,
        "message": f"'{original_name}' has been safely filed away in the cupboard."
    }


@app.get("/documents")
def list_documents():
    """Returns list of all documents stored in the cupboard."""
    docs = db.get_all_documents()
    return {"documents": docs, "total": len(docs)}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    """Deletes a document from SQLite, uploads directory, and ChromaDB."""
    doc = db.delete_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in the cupboard.")

    # Remove physical file if present
    file_path = UPLOADS_DIR / doc["filename"]
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass

    # Remove chunks from ChromaDB
    try:
        rag.delete_document(doc["original_name"])
    except Exception:
        pass

    return {
        "success": True,
        "message": f"'{doc['original_name']}' has been removed from the cupboard."
    }


@app.post("/ask")
def ask_question(body: AskRequest):
    """
    Finds the top 4 relevant chunks in ChromaDB, prompts Gemini
    with strict context constraints, and returns answer + citations.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result = rag.query_rag(question, top_k=4)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
