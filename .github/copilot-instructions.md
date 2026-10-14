# Copilot Instructions — CoolRoute

## Repository state
Currently the repo contains only `plan.md`: a phased (Phase 0–8) learning plan for a **cold-chain logistics AI dispatch assistant**. No code, build, lint, or test config exists yet. Treat `plan.md` as the spec; follow its module layout and decisions when generating code, and update it if the design changes.

## Planned stack (fixed decisions in `plan.md`)
Python 3.11+, LangGraph (`create_react_agent` first, later a custom graph), Ollama (`qwen3:4b` for generation, `nomic-embed-text` for 768-dim embeddings), PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`) accessed via SQLAlchemy + `psycopg` v3 (no ODBC), `langchain-postgres` for vectors, Streamlit UI, Open-Meteo + NWS weather, Docker Compose, GitHub Actions deploying to an Azure VM.

## Commands (per plan; none exist yet)
- Venv: `python -m venv .venv`
- UI: `streamlit run app/main.py`
- Seed DB (rebuildable in one command): `python scripts/seed.py`; data generator `scripts/generate_data.py`
- RAG ingestion (idempotent, hash-based): `python -m rag.ingest`
- Proactive monitor loop: `python scripts/monitor.py`
- Tests: `pytest`; single test: `pytest tests/test_x.py::test_name`
- Lint (CI): `ruff`

## Architecture (big picture)
- `app/` Streamlit (Dashboard, Chat, Audit pages); `agent/` LangGraph (`graph.py`, `state.py`, `prompts.py`, `tools/{sql,weather,rag,risk}_tool.py`); `rag/` ingestion + retrieval; `db/` schema, connection, queries, audit logger; `data/policies/` rulebooks (public regs + hand-written mock SOPs); `scripts/` generators/one-offs.
- One PostgreSQL holds telemetry, audit tables, and pgvector chunks (`policy_chunks`, HNSW cosine index). Use the same embedding model for indexing and querying.
- Agent flow evolves: ReAct agent for open-ended Q&A; a custom graph for structured risk review: `router → data_gather → risk_assess → decision → validate → explain`. The validate node loops back unless the recommendation cites ≥1 policy and a risk score exists; guard with `recursion_limit`.
- Audit: callback handler (`AuditCallbackHandler`) writes append-only `AuditEvents` with a SHA256 hash chain (`hash = SHA256(prev_hash + canonical_json(event))`); `verify_chain()` detects tampering.

## Key conventions
- **Compute numbers in code, let the LLM explain them.** Risk score (0–100; LOW <30, MEDIUM 30–59, HIGH 60–79, CRITICAL ≥80) is pure, unit-testable Python in `risk_tool.py` returning a structured object (score, level, per-factor breakdown, evidence). Never let the LLM invent scores or temps.
- **SQL safety:** `run_sql` allows a single `SELECT` only (parse with `sqlglot`, dialect `postgres`), runs via a read-only `agent_ro` role with no access to audit tables, in a read-only transaction, with `LIMIT 200` and `statement_timeout`. Prefer fixed parameterized tools where possible.
- **Tool outputs must be compact** (summarize/aggregate; no huge JSON); tool docstrings act as prompts.
- **Citations:** every policy claim cites a source (e.g. `[SOP-002 §3, p.4]`); if none found, say so.
- **Deterministic testing:** `WEATHER_MODE=mock` uses JSON fixtures; HTTP tests use recorded fixtures; agent evals assert tool *trajectory*, not exact text.
- **Planted scenarios** (seeded deterministically; don't break them): Truck 284 (vaccines, Phoenix, rising compressor load → HIGH), Truck 452 (seafood, storm, long ETA), Truck 101 (door-open excursion), Truck 007 (healthy control, must NOT be flagged), a frozen shipment drifting −20→−16°C.
- Cargo profiles: Vaccines 2–8°C, Seafood 0–2°C, Frozen ≤ −18°C, Dairy 1–4°C, Produce 4–10°C, Chemicals 15–25°C.
- Only call the LLM for HIGH+ cases in the monitor loop (cost control).
- Config via `.env` (`DB_CONN`, `OLLAMA_BASE_URL`, optional `LANGSMITH_API_KEY`); never commit secrets. `.gitignore`: `.venv`, `.env`, `__pycache__`, `pgdata/`, `data/raw/`.
- Streamlit: cache queries with `@st.cache_data(ttl=60)`; use a `thread_id` per session for the LangGraph checkpointer.
- Each phase ends with a Checkpoint and a git tag (`v0.1`…`v1.0`); module notes go in `docs/lectures/`.
