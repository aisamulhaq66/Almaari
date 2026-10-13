import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, Header, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import rag

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory session store mapping token -> user dict
SESSIONS = {}

app = FastAPI(
    title="Almaari API",
    description="Backend API for Almaari - AI-powered document archive portal with Role-Based Access Control.",
    version="2.0.0"
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


# Authentication Dependency
def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Reads 'Authorization: Bearer <token>' header and returns user dict.
    Raises HTTP 401 if token is missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header."
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format. Expected 'Bearer <token>'."
        )

    token = parts[1].strip()
    user = SESSIONS.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again."
        )

    return user


@app.get("/")
def root():
    return {
        "portal": "Almaari",
        "tagline": "Apni files se poochho. (Ask your files anything.)",
        "status": "online"
    }


@app.post("/login")
def login(creds: LoginRequest):
    """
    Authenticates username/password in SQLite.
    Returns session token plus user role.
    """
    user = db.authenticate_user(creds.username.strip(), creds.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password. The cupboard remains locked."
        )

    # Generate token and store in session dict
    token = f"almaari_{user['username']}_{uuid.uuid4().hex[:12]}"
    SESSIONS[token] = user

    return {
        "success": True,
        "username": user["username"],
        "role": user["role"],
        "token": token
    }


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    allowed_roles: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Accepts PDF or TXT file and comma-separated allowed_roles.
    Validates roles against executive, hr, employee (or 'everyone').
    Saves file, indexes chunks into ChromaDB with boolean role metadata,
    and records in SQLite with uploader information.
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

    # Validate and normalize allowed_roles
    if not allowed_roles or not allowed_roles.strip():
        raise HTTPException(status_code=400, detail="allowed_roles cannot be empty.")

    VALID_ROLES = {"executive", "hr", "employee"}
    raw_roles = [r.strip().lower() for r in allowed_roles.split(",") if r.strip()]

    if not raw_roles:
        raise HTTPException(status_code=400, detail="allowed_roles cannot be empty.")

    if "everyone" in raw_roles:
        parsed_roles = ["executive", "hr", "employee"]
    else:
        for r in raw_roles:
            if r not in VALID_ROLES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid role '{r}'. Allowed roles are: executive, hr, employee, or everyone."
                )
        # Deduplicate while preserving order
        parsed_roles = list(dict.fromkeys(raw_roles))

    # Generate safe local filename
    safe_filename = f"{uuid.uuid4().hex[:8]}_{original_name}"
    save_path = UPLOADS_DIR / safe_filename

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    file_size = save_path.stat().st_size

    # Index into ChromaDB with boolean role flags
    try:
        chunk_count = rag.index_document(
            str(save_path),
            doc_name=original_name,
            allowed_roles=parsed_roles
        )
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to process and index document: {str(e)}")

    # Record in SQLite with allowed_roles and uploader
    doc_id = db.add_document(
        filename=safe_filename,
        original_name=original_name,
        file_size=file_size,
        chunk_count=chunk_count,
        allowed_roles=",".join(parsed_roles),
        uploader=current_user["username"]
    )

    return {
        "id": doc_id,
        "filename": safe_filename,
        "original_name": original_name,
        "file_size": file_size,
        "chunk_count": chunk_count,
        "allowed_roles": ",".join(parsed_roles),
        "uploader": current_user["username"],
        "message": f"'{original_name}' has been safely filed away in the cupboard."
    }


@app.get("/documents")
def list_documents(current_user: dict = Depends(get_current_user)):
    """
    Returns only documents the current user's role is allowed to see,
    including each document's allowed_roles and uploader.
    """
    docs = db.get_all_documents(user_role=current_user["role"])
    return {"documents": docs, "total": len(docs)}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, current_user: dict = Depends(get_current_user)):
    """
    Deletes a document from SQLite, uploads directory, and ChromaDB.
    Allowed only for the uploader or an executive. Otherwise returns 403.
    """
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in the cupboard.")

    # Authorization check
    is_uploader = doc["uploader"] == current_user["username"]
    is_executive = current_user["role"] == "executive"

    if not (is_uploader or is_executive):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only the uploader or an executive can delete this document."
        )

    # Perform deletion
    db.delete_document_by_id(doc_id)

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
def ask_question(body: AskRequest, current_user: dict = Depends(get_current_user)):
    """
    Pre-filters ChromaDB by the user's role BEFORE sending context to Gemini.
    Never fetches chunks invisible to the user's role.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result = rag.query_rag(question, user_role=current_user["role"], top_k=4)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
