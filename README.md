# FounderSignal

> **AI Operating Companion for Founders of Small Businesses & Startups**

FounderSignal connects business conversations, decisions, commitments, people, projects, and delivery evidence to give founders clear, verified visibility over what is actually happening across their business.

---

## 1. Core Principles

1. **Evidence over assumptions:** Every metric, decision, and extracted signal links directly to source evidence (transcripts, meeting notes, project records).
2. **Human approval before important actions:** The system never autonomously executes financial, HR, or contractual decisions.
3. **Every extracted commitment must have a source:** Excerpts, speakers, timestamps, and confidence scores are attached to all extracted commitments.
4. **Distinguish facts vs. inferred vs. unknown:** Clear separation between confirmed facts, model inferences with confidence scores, and unknown information requiring clarification.
5. **Privacy and security by design:** Raw audio and conversation records are isolated and protected. Sensitive business data is never logged or exposed.
6. **Simple UX for non-technical business owners:** Jargon-free, intuitive interface built for founders.
7. **Modular, maintainable, and testable architecture:** Clean boundaries between APIs, database models, business logic services, and external AI provider adapters.

---

## 2. Architecture & Monorepo Structure

```
foundersignal/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (health, v1 endpoints)
│   │   ├── core/             # Configuration, logging, exceptions, database engine
│   │   ├── models/           # SQLAlchemy 2.x declarative models (audit, timestamp mixins)
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── services/         # Business logic layer
│   │   ├── providers/        # External AI adapters with mock capability for dev
│   │   │   ├── stt/          # Gnani Prisma Speech-to-Text adapter
│   │   │   ├── timbre/       # Timbre Text-to-Speech adapter
│   │   │   └── llm/          # Structured signal extraction provider
│   │   └── main.py           # FastAPI application entrypoint with structured error handling
│   ├── alembic/              # Database migration environment
│   ├── tests/                # Pytest test suite (health, exceptions, providers)
│   ├── pyproject.toml        # Dependencies, Ruff, and Pytest configuration
│   └── .env.example          # Backend environment variable template
│
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router (layout, dashboard placeholder, styling)
│   │   ├── components/       # shadcn/ui components & responsive shell layout (Sidebar, Header)
│   │   └── lib/              # Utility helpers (cn, class variance authority)
│   ├── package.json          # Frontend dependencies and scripts
│   ├── tsconfig.json         # Strict TypeScript configuration
│   ├── tailwind.config.ts    # Tailwind styling system
│   └── .env.example          # Frontend environment variable template
│
├── docker-compose.yml        # Local PostgreSQL container definition
├── AGENTS.md                 # Agent guidelines, rules, and technical conventions
├── .gitignore                # Comprehensive exclusions (credentials, audio, caches)
└── README.md                 # Project documentation
```

---

## 3. Technology Stack

- **Frontend:** Next.js (App Router), TypeScript (strict mode), Tailwind CSS, shadcn/ui, Lucide Icons.
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic v2, pydantic-settings, Alembic, psycopg 3.
- **Database:** PostgreSQL 16.
- **Code Quality & Testing:** Ruff, Pytest, ESLint, TypeScript compiler (`tsc`).
- **AI Integrations:**
  - **Gnani Prisma:** Speech-to-Text (STT) transcription engine (*Note: Not Prisma ORM*).
  - **Timbre:** Voice analytics and text-to-speech engine.
  - **LLM Provider:** Provider-agnostic structured extraction layer.

---

## 4. Prerequisites

- **Python:** 3.12 or newer (tested through Python 3.14)
- **Node.js:** v20+ (tested on Node v24.21.0) and `npm`
- **Docker & Docker Compose:** For running the local PostgreSQL database

---

## 5. Getting Started & Installation

### Step 1: Clone and Configure Environment

```bash
git clone <repository-url> foundersignal
cd foundersignal

# Configure backend environment
cp backend/.env.example backend/.env

# Configure frontend environment
cp frontend/.env.example frontend/.env
```

### Step 2: Start the Local Database

```bash
docker compose up -d
```

Verify that the database is healthy:
```bash
docker compose ps
```

### Step 3: Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode with development tools
pip install --upgrade pip
pip install -e ".[dev]"

# Run Alembic migrations
alembic current
```

### Step 4: Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install
```

---

## 6. Local Development Commands

### Start Backend API Server

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/api/v1/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`

### Start Frontend Application

```bash
cd frontend
npm run dev
```
- Access Cockpit: `http://localhost:3000`

---

## 7. Quality & Testing Commands

### Backend Verification

```bash
cd backend
source .venv/bin/activate

# Run Pytest suite
pytest -v

# Run Ruff linter and code style checks
ruff check .
```

### Frontend Verification

```bash
cd frontend

# Run strict TypeScript type check
npm run typecheck

# Run Next.js linting
npm run lint
```
