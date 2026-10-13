import sqlite3
import hashlib
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "almaari.db"


def get_db_connection():
    """Returns a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str = None) -> str:
    """Hashes a password using SHA-256 with a salt."""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against the stored salt:hash string."""
    try:
        salt, _ = stored_hash.split(":", 1)
        return hash_password(password, salt) == stored_hash
    except Exception:
        return False


def init_db():
    """Initializes tables, migrates missing columns, and seeds demo users."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            allowed_roles TEXT NOT NULL DEFAULT 'executive,hr,employee',
            uploader TEXT NOT NULL DEFAULT 'admin',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check and migrate columns if upgrading from old schema
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row["name"] for row in cursor.fetchall()]
    if "role" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'")

    cursor.execute("PRAGMA table_info(documents)")
    doc_columns = [row["name"] for row in cursor.fetchall()]
    if "allowed_roles" not in doc_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN allowed_roles TEXT NOT NULL DEFAULT 'executive,hr,employee'")
    if "uploader" not in doc_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN uploader TEXT NOT NULL DEFAULT 'admin'")

    # Seed the three requested demo users
    demo_users = [
        ("executive", "executive123", "executive"),
        ("hr", "hr123", "hr"),
        ("employee", "employee123", "employee"),
        ("admin", "almaari123", "executive"),  # Preserved for backward compatibility
    ]

    for uname, pwd, role in demo_users:
        cursor.execute("SELECT id FROM users WHERE username = ?", (uname,))
        row = cursor.fetchone()
        if not row:
            hashed = hash_password(pwd)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (uname, hashed, role)
            )
        else:
            # Ensure correct role is set
            cursor.execute("UPDATE users SET role = ? WHERE username = ?", (role, uname))

    conn.commit()
    conn.close()


def authenticate_user(username: str, password: str):
    """Authenticates username and password against SQLite, returning user dict with role."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and verify_password(user["password_hash"], password):
        return {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    return None


def add_document(filename: str, original_name: str, file_size: int, chunk_count: int, allowed_roles: str, uploader: str) -> int:
    """Adds a document record with access roles and uploader."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Remove existing record with same original_name if re-uploaded
    cursor.execute("DELETE FROM documents WHERE original_name = ?", (original_name,))

    cursor.execute("""
        INSERT INTO documents (filename, original_name, file_size, chunk_count, allowed_roles, uploader, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (filename, original_name, file_size, chunk_count, allowed_roles, uploader, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def get_all_documents(user_role: str = None) -> list[dict]:
    """
    Retrieves document records. If user_role is provided,
    filters only documents the user's role is allowed to see.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, original_name, file_size, chunk_count, allowed_roles, uploader, uploaded_at FROM documents ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        doc = dict(row)
        roles = [r.strip().lower() for r in doc.get("allowed_roles", "").split(",") if r.strip()]
        if user_role is None or user_role.lower() in roles:
            results.append(doc)

    return results


def get_document_by_id(doc_id: int):
    """Retrieves single document by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, original_name, file_size, chunk_count, allowed_roles, uploader, uploaded_at FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_document_by_id(doc_id: int):
    """Deletes a document record by ID and returns the deleted doc info."""
    doc = get_document_by_id(doc_id)
    if not doc:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return doc


# Run init on module load
init_db()
