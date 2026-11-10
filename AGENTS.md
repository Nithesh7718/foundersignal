# AGENTS.md - FounderSignal Engineering and AI Guidelines

Welcome to **FounderSignal**, an AI operating companion for founders of small businesses and startups.
FounderSignal connects business conversations, decisions, commitments, people, projects, and delivery evidence to help founders understand what is actually happening in their business.

---

## 1. Core Product Principles

1. **Evidence over assumptions:** Every claim, metric, and inference must link back to underlying business evidence (transcripts, meeting notes, project logs).
2. **Human approval before important business actions:** The AI does not autonomously execute high-stakes operations. Approvals must be clear and auditable.
3. **Every extracted commitment must have a source:** Attach exact transcript excerpts, speakers, timestamps, and confidence scores to commitments.
4. **Distinguish facts vs. inferred vs. unknown:**
   - *Confirmed Facts:* Explicit statements verified or confirmed by the founder.
   - *Inferred Information:* Probabilistic extractions with confidence ratings.
   - *Unknown Information:* Explicitly cataloged missing details that require clarification.
5. **Privacy and security by design:** Raw audio and conversation transcripts contain sensitive business secrets. Never log credentials or expose sensitive payloads.
6. **Simple UX for non-technical business owners:** Interfaces must be clean, human-readable, and free from confusing AI jargon.
7. **Modular, maintainable, and testable architecture:** Clean boundaries between API, models, business services, and AI provider integrations.

---

## 2. Technology Stack & Key Definitions

- **Backend:** Python 3.12+ (tested through 3.14), FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, pydantic-settings, Pytest, Ruff.
- **Frontend:** Next.js (App Router), TypeScript (strict mode), Tailwind CSS, shadcn/ui.
- **Database:** PostgreSQL (with `psycopg` 3.x driver).
- **AI Integrations:**
  - **Gnani Prisma:** Speech-to-Text (STT) transcription engine.
    > *CRITICAL:* Gnani Prisma is an STT service. **Do NOT confuse it with Prisma ORM.**
  - **Timbre:** Voice analytics / text-to-speech provider.
  - **LLM Layer:** Provider abstraction supporting structured outputs with confidence scoring.

---

## 3. Engineering & Architectural Rules

- **Strict Typing:** All TypeScript must pass `tsc --noEmit` under strict mode. All Python services, models, and schemas must use typed signatures.
- **Separation of Concerns:**
  - `api/`: Request routing and HTTP handling only.
  - `models/`: SQLAlchemy declarative tables representing the database schema.
  - `schemas/`: Pydantic data validation and serialization.
  - `services/`: Core business logic and orchestration.
  - `providers/`: External service adapters (Gnani Prisma STT, Timbre, LLM providers) with mock support for development.
  - `core/`: Config, database sessions, security, structured logging.
- **Credential Safety:** Never hardcode API keys or passwords. Use `.env.example` templates and load configs via `pydantic-settings`.
- **Mocking:** External APIs may only be mocked when `MOCK_PROVIDERS=true` or in automated testing fixtures. Production mode must reject unconfigured credentials gracefully.
- **Do not introduce unnecessary microservices:** FounderSignal is structured as a clean, cohesive modular monolith.

---

## 4. AI Rules

- Never treat unverified AI output as confirmed business data.
- Always require user confirmation for extracted commitments before committing them to operational records.
- Never autonomously send messages, initiate financial transactions, or execute HR/contractual actions.

---

## 5. Development Workflow

1. Inspect the workspace before modifying.
2. Outline plans and explain technical rationale in understandable language.
3. Implement features incrementally.
4. Run tests and type checks (`pytest`, `ruff check`, `npm run lint`, `tsc`).
5. Verify changes end-to-end before marking milestones complete.
