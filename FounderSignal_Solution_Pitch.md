# FounderSignal
**Turning spoken business updates into accountable execution intelligence**

### Problem
Small-business founders and teams often communicate through voice notes and informal conversations. Important decisions, commitments, deadlines and follow-ups get buried in these conversations. Manually converting them into structured records is time-consuming, while automated summaries can introduce unsupported assumptions.

### Solution
FounderSignal is an evidence-first, voice-driven business execution intelligence platform. It transforms spoken business updates into structured, attributable information that helps founders track what was discussed, what was committed to, and what requires follow-up.

### How it works
1. **Capture:** A user uploads or records a business voice update.
2. **Transcribe:** Gnani AI's Prisma speech-to-text model converts audio into text.
3. **Structure:** The platform stores transcripts and links them to conversations and business workspaces.
4. **Track:** Commitments can be associated with their source conversations, creating an evidence trail for follow-up.
5. **Review:** Users remain in control of decisions and corrections rather than relying on unsupported AI-generated conclusions.

### Use of Gnani AI
FounderSignal integrates **Gnani Prisma v3.0** for speech-to-text transcription, with a planned v2.5 fallback. The architecture supports synchronous REST transcription for short recordings and asynchronous Batch processing for longer recordings.

### Technology
- **Backend:** Python, FastAPI, PostgreSQL, SQLAlchemy and Alembic
- **Frontend:** Next.js, React and TypeScript
- **AI integration:** Gnani Prisma speech-to-text API
- **Infrastructure:** Persistent transcription jobs, worker processing, retry handling and multi-tenant workspace isolation

### What makes it different
FounderSignal prioritises evidence and accountability over generic AI summaries. It is designed around attributable transcripts, traceable commitments, tenant isolation, human review and honest handling of transcription uncertainty.

### Current implementation
The project includes authentication, workspace isolation, audio handling, persistent transcription jobs, REST and Batch processing workflows, worker lease protection, retry and reconciliation mechanisms, and automated backend tests.

### Vision
To help founders and small-business teams turn everyday conversations into reliable business execution records—without losing the context or evidence behind important decisions.