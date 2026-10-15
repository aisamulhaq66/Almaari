# Almaari (الماری) — AI Document Search & Private Archive Portal

> *"Apni files se poochho."* — *(Ask your files anything.)*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20+%20Vite-61DAFB?style=flat-square&logo=react)](https://react.dev/)
[![Framer Motion](https://img.shields.io/badge/Animations-Framer%20Motion-black?style=flat-square&logo=framer)](https://www.framer.com/motion/)
[![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB-red?style=flat-square)](https://www.trychroma.com/)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-4285F4?style=flat-square&logo=google)](https://deepmind.google/technologies/gemini/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square&logo=sqlite)](https://www.sqlite.org/)

**Almaari (الماری)** is an AI-powered document search portal designed as a private, role-aware archival cupboard for company documents. Instead of navigating through folders and 50-page handbooks, team members ask questions in plain natural language and receive instant, source-attributed answers grounded strictly in uploaded company papers.

Built with a **zero-overengineering** philosophy: a high-performance Python backend paired with a bespoke, tactile editorial frontend.

---

## Key Highlights

- **Strict Retrieval-Augmented Generation (RAG):** The AI answers *only* from indexed text chunks. If information is missing from the archive, it transparently responds *"I don't know."* without hallucinating.
- **Database-Level Vector Pre-Filtering (Zero Data Leakage):** ChromaDB queries are filtered on chunk metadata booleans (`where={"role_<user_role>": True}`) *before* context is sent to Gemini. Unauthorized documents are never read or retrieved.
- **"A Private Archive Room" Aesthetic:** Deliberately departs from generic AI web design (no purple gradients, glowing orbs, or glassmorphism). Instead, it features warm paper tones, thin ink borders, hard offset shadows, Google Fonts *Fraunces* & *Instrument Sans*, and tactile animations.
- **Micro-Interactions & Gestures:** Custom animated SVG cupboard door with 3D hinge swing on login, reactive drag-and-drop upload shelf, 4-chip role selector, swipe-to-delete cards, word-by-word typewriter streaming, and press-and-hold context inspection modals.

---

## System Architecture

```text
               ┌────────────────────────────────────────────────────────┐
               │             React 18 + Vite (Port 5173)                │
               │  - Archival Design Tokens & Fraunces / Instrument Sans │
               │  - Framer Motion gestures (swipe-to-delete, chips)     │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                  HTTP + Bearer Token
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │              FastAPI Backend (Port 8000)               │
               │  - Token authentication & reload-resilient sessions    │
               │  - Document parsing (.pdf, .txt) & sliding chunking    │
               │  - Role validation & authorization guards (401 / 403)  │
               └───────────┬────────────────────────┬───────────────────┘
                           │                        │
             Metadata & Credential Check     Vector Pre-Filtering (where={"role": True})
                           │                        │
                           ▼                        ▼
               ┌───────────────────────┐ ┌──────────────────────────────┐
               │  SQLite (almaari.db)  │ │   ChromaDB (chroma_db/)      │
               │  - users & salt hashes│ │  - 384d all-MiniLM-L6-v2     │
               │  - docs & uploaders   │ │  - boolean role chunk tags   │
               └───────────────────────┘ └──────────────┬───────────────┘
                                                        │
                                            Grounded Context Chunks
                                                        │
                                                        ▼
                                         ┌──────────────────────────────┐
                                         │   Google Gemini 2.5 Flash    │
                                         │  - Bounded prompt generation │
                                         │  - Source attribution        │
                                         └──────────────────────────────┘
```

---

## Role-Based Access Control (RBAC) Matrix

Every uploaded document is tagged with allowed viewing roles (`executive`, `hr`, `employee`, or `everyone`).

| Role | Viewing Documents (`/documents`) | Asking Questions in Chat (`/ask`) | File Uploads (`/upload`) | Deletion Rights (`DELETE`) |
| :--- | :--- | :--- | :--- | :--- |
| **Executive** | All files marked for Executives or Everyone | Searches across all Executive & Everyone files | Uploads with any role combination | **Full admin privilege:** Can delete any file |
| **HR** | HR and Everyone files (Executive-only hidden) | Searches strictly within HR & Everyone files | Uploads with any role combination | Can only delete files uploaded by HR |
| **Employee** | General & Everyone files (HR/Exec-only hidden) | Searches strictly within Employee-cleared files | Uploads with any role combination | Can only delete files uploaded by Employee |

> **Security Note:** If an employee asks *"What is the HR Director's salary?"*, ChromaDB excludes confidential HR chunks at the vector query stage. Gemini never receives the chunk text and returns *"I don't know."*

---

## Tech Stack & Engineering Decisions

### Backend
- **FastAPI:** Asynchronous, lightweight Python web framework with automated OpenAPI/Swagger documentation.
- **SQLite:** Serverless relational storage for credentials, roles, and document metadata.
- **`sentence-transformers/all-MiniLM-L6-v2`:** Runs locally on CPU/GPU to generate 384-dimensional dense vectors without paying per-token embedding fees.
- **ChromaDB:** Local vector database with persistent storage and metadata filtering.
- **Google Gemini 2.5 Flash:** Low-latency, cost-effective LLM with high context compliance.

### Frontend
- **React 18 + Vite:** Fast hot-module reloading and optimized bundling.
- **Framer Motion:** Declarative physics-based animations (hinged door swing, spring chips, drag gestures, staggered entrances).
- **Vanilla CSS Tokens:** Zero UI component libraries (no Tailwind, Bootstrap, or Material UI). Clean CSS custom properties (`--paper`, `--ink`, `--verdigris`, `--vermilion`, `--mustard`).
- **Typography:** Google Fonts *Fraunces* (editorial serif headlines), *Instrument Sans* (body), and *JetBrains Mono* (code, citations, metadata).

---

## Project Structure

```text
Almaari/
├── backend/
│   ├── main.py        # FastAPI app, Bearer auth, REST routes (/login, /upload, /documents, /ask)
│   ├── db.py          # SQLite schema, migration helpers, salted SHA-256 password hashing
│   └── rag.py         # Text extraction, chunking, ChromaDB vector index, Gemini prompting
├── frontend/          # React + Vite application
│   ├── src/
│   │   ├── components/
│   │   │   ├── CupboardLogo.jsx # Custom SVG cupboard door with 3D spring hinge
│   │   │   └── Navbar.jsx       # Archival wordmark, tagline, active role stamp
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx    # Staggered entrance, animated cupboard door
│   │   │   ├── DocumentsPage.jsx# Drag-and-drop shelf, 4-chip role selector, swipe-to-delete
│   │   │   └── ChatPage.jsx     # Word-by-word typewriter streaming, chunk preview modal
│   │   ├── api.js               # Resilient API client with Bearer auth & proxy fallbacks
│   │   ├── App.jsx              # Session routing & page transition orchestration
│   │   └── index.css            # Archival design system, grain overlay, hard offset shadows
│   ├── vite.config.js
│   └── package.json
├── uploads/           # Physical document storage
├── requirements.txt   # Python backend dependencies
└── .env.example       # Environment configuration template
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- A free Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/))

### 1. Clone the Repository
```bash
git clone https://github.com/aisamulhaq66/Almaari-base-1.git
cd Almaari-base-1
```

### 2. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Open .env and add your GEMINI_API_KEY:
# GEMINI_API_KEY=your_gemini_api_key_here

# Start the FastAPI server
cd backend
python -m uvicorn main:app --reload --port 8000
```
Backend will be live at `http://127.0.0.1:8000`. Interactive Swagger API docs: `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## Demo Credentials

For quick evaluation, seed demo accounts are pre-configured:

| Username | Password | Role | Access Level |
| :--- | :--- | :--- | :--- |
| **`executive`** | `executive123` | `executive` | Full visibility, can delete any document |
| **`hr`** | `hr123` | `hr` | HR + General documents, deletes own files |
| **`employee`** | `employee123` | `employee` | General documents only, deletes own files |
| **`admin`** | `almaari123` | `executive` | Administrative fallback |

---

## Design System Tokens

```css
:root {
  --paper: #EDE6D3;         /* Warm background texture */
  --paper-card: #FAF8F2;    /* Archival card surface */
  --ink: #151A17;           /* High-contrast ink text & borders */
  --ink-muted: #535C56;     /* Secondary editorial text */
  --verdigris: #2E6B5E;     /* Primary verdigris green accent */
  --vermilion: #E1452C;     /* Destructive actions & active chips */
  --mustard: #D8A23A;       /* Highlights, brass keyholes & tags */
  --border-ink: 1.5px solid var(--ink);
  --shadow-sm: 2px 2px 0px var(--ink);
  --shadow-md: 3px 3px 0px var(--ink);
}
```

---

## License
MIT License. Created as a student portfolio project exploring tactile human-computer interaction and local-first RAG systems.
