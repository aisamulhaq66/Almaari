import os
import re
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai
from pypdf import PdfReader

# Load environment variables (.env)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ChromaDB persistence directory
CHROMA_DATA_PATH = str(BASE_DIR / "chroma_db")

# Embedding model: sentence-transformers/all-MiniLM-L6-v2
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def get_chroma_collection():
    """Initializes and returns the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
    collection = client.get_or_create_collection(
        name="almaari_documents",
        embedding_function=embedding_func
    )
    return collection


def migrate_existing_chunks():
    """Ensures any existing chunks from previous version have all three roles enabled."""
    try:
        collection = get_chroma_collection()
        all_items = collection.get(include=["metadatas"])
        ids = all_items.get("ids", [])
        metadatas = all_items.get("metadatas", [])
        updated_ids = []
        updated_metas = []

        for item_id, meta in zip(ids, metadatas):
            if "role_executive" not in meta or "role_hr" not in meta or "role_employee" not in meta:
                new_meta = dict(meta)
                new_meta["role_executive"] = True
                new_meta["role_hr"] = True
                new_meta["role_employee"] = True
                updated_ids.append(item_id)
                updated_metas.append(new_meta)

        if updated_ids:
            collection.update(ids=updated_ids, metadatas=updated_metas)
    except Exception:
        pass


def extract_text(file_path: str) -> str:
    """Extracts raw text from a TXT or PDF file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        reader = PdfReader(str(path))
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n\n".join(pages_text)

    else:
        raise ValueError(f"Unsupported file format '{ext}'. Only .pdf and .txt are supported.")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Splits text into chunks of ~500 words with 50-word overlap."""
    words = re.findall(r'\S+', text)
    if not words:
        return []

    chunks = []
    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size

    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break

    return chunks


def index_document(file_path: str, doc_name: str = None, allowed_roles: list[str] = None) -> int:
    """
    Extracts text, chunks it, and stores chunks in ChromaDB.
    Attaches role_executive, role_hr, and role_employee booleans to metadata for pre-filtering.
    """
    path = Path(file_path)
    filename = doc_name or path.name

    text = extract_text(file_path)
    chunks = chunk_text(text, chunk_size=500, overlap=50)

    if not chunks:
        return 0

    collection = get_chroma_collection()

    # Clear previous chunks for this document if re-uploaded
    try:
        collection.delete(where={"source": filename})
    except Exception:
        pass

    # Normalize roles (default to all three if not specified)
    roles_set = set(r.lower().strip() for r in allowed_roles) if allowed_roles else {"executive", "hr", "employee"}
    role_exec = "executive" in roles_set
    role_hr = "hr" in roles_set
    role_emp = "employee" in roles_set

    # Prepare batch data with role boolean flags
    ids = [f"{filename}_{idx}" for idx in range(len(chunks))]
    metadatas = [{
        "source": filename,
        "chunk_index": idx,
        "role_executive": role_exec,
        "role_hr": role_hr,
        "role_employee": role_emp
    } for idx in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        metadatas=metadatas
    )

    return len(chunks)


def delete_document(filename: str):
    """Removes all indexed chunks associated with the given file name."""
    collection = get_chroma_collection()
    collection.delete(where={"source": filename})


def query_rag(query: str, user_role: str = "employee", top_k: int = 4) -> dict:
    """
    Finds the top 4 relevant chunks pre-filtered strictly by user_role in ChromaDB.
    Chunks invisible to the user's role are NEVER fetched.
    """
    collection = get_chroma_collection()

    count = collection.count()
    if count == 0:
        return {
            "answer": "I don't know.",
            "sources": [],
            "chunks": []
        }

    # Build ChromaDB 'where' filter on role boolean
    valid_roles = ["executive", "hr", "employee"]
    role_key = f"role_{user_role.lower()}" if user_role.lower() in valid_roles else "role_employee"
    role_filter = {role_key: True}

    # Query ChromaDB with strict pre-filter
    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            where=role_filter
        )
    except Exception:
        # If filter has no matches or error
        return {
            "answer": "I don't know.",
            "sources": [],
            "chunks": []
        }

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    # If no relevant chunks match the user's role
    if not documents:
        return {
            "answer": "I don't know.",
            "sources": [],
            "chunks": []
        }

    # Format context for Gemini
    context_blocks = []
    sources = []
    chunks_info = []

    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        source_name = meta.get("source", "Unknown file")
        context_blocks.append(f"[Document: {source_name}]\n{doc}")
        if source_name not in sources:
            sources.append(source_name)
        chunks_info.append({
            "source": source_name,
            "chunk_index": meta.get("chunk_index", i),
            "text": doc
        })

    combined_context = "\n\n---\n\n".join(context_blocks)

    prompt = f"""Context:
{combined_context}

Question:
{query}

Instruction:
Answer only from the context below. If the answer is not there, say you don't know."""

    # Generate answer with Gemini
    load_dotenv(BASE_DIR / ".env", override=True)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "answer": "Gemini API key is not configured in .env. Please set GEMINI_API_KEY.",
            "sources": sources,
            "chunks": chunks_info
        }

    try:
        genai.configure(api_key=api_key)
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            answer = response.text.strip()
        except Exception:
            model = genai.GenerativeModel("gemini-3.8-flash")
            response = model.generate_content(prompt)
            answer = response.text.strip()
    except Exception as e:
        answer = f"Error generating answer from Gemini: {e}"

    return {
        "answer": answer,
        "sources": sources,
        "chunks": chunks_info
    }


# Run migration of existing chunks on module import
migrate_existing_chunks()
