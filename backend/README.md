# AI Career Copilot - backend

Phase 1: FastAPI skeleton + configurable LLM provider (Gemini by default).
Phase 2: resume upload (PDF/DOCX) -> text extraction -> LLM -> validated structured JSON.
Phase 3: job description analysis + resume-to-job matching (deterministic score, LLM suggestions).
Phase 4: SQLite application tracker (status history + optional match snapshot). Never stores resumes.
Phase 6: knowledge base (RAG): your own career notes -> chunks -> local embeddings -> Chroma -> grounded answers.
Phase 7: agent: an LLM loop that can call read-only tools (tracker + notes) before answering.
Phase 8: MCP server: the same read-only tools, published through the Model Context Protocol (stdio).
Phase 9: interview preparation: a fixed workflow that turns a saved job match + your notes into a prep pack.

Requires Python 3.10+.

## Setup
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt  # re-run this after updating to Phase 2: new packages were added
    cp .env.example .env             # Windows: copy .env.example .env
    # then edit .env and set GEMINI_API_KEY

## Run tests (no API key needed)
    python -m pytest -v

## Try the real thing
    python -m scripts.check_llm                          # Phase 1: provider smoke test
    python -m scripts.parse_resume path/to/resume.pdf    # Phase 2: full pipeline, real LLM
    python -m scripts.match_job path/to/resume.pdf samples/sample_job_description.txt   # Phase 3
    python -m scripts.rag_demo "How did I reduce deployment time?" --ask   # Phase 6 (first run downloads ~80 MB)
    python -m scripts.agent_demo "Which of my applications is furthest along?"   # Phase 7: prints every step

## Run the server
    uvicorn app.main:app --reload
    # open http://127.0.0.1:8000/docs
    #   POST /resumes/parse   upload a resume
    #   POST /jobs/analyze    paste a job description
    #   POST /jobs/match      paste the "parsed" object from /resumes/parse + a job description
    #   /applications ...     the tracker (create, list, update, status, match snapshot, delete)
    #   /knowledge/...        add notes, search them, and ask questions answered from them
    #   POST /agent/ask       ask a question; the agent may look things up first (see the steps in the reply)
    # The database file is created automatically at backend/career_copilot.db on first start.

## How structured output works (Phase 2)
    services/resume/extractor.py   file bytes -> raw text (validates type, size, magic bytes)
    services/resume/cleaner.py     tidy the text
    services/resume/prompts.py     the prompt (rules + format example)
    services/llm/json_utils.py     reply text -> Python dict (handles ```json fences, chatter)
    services/llm/structured.py     ask -> extract -> validate (Pydantic) -> retry once with feedback
    services/resume/parser.py      resume prompt + ParsedResume schema, glued to structured.py

## How matching works (Phase 3) - "code for logic, LLM for language"
    services/job/analyzer.py     job text -> JobAnalysis        (LLM, reuses generate_structured)
    services/job/skills.py       normalize names ("ReactJS" -> "react"), whole-word text search   (pure code)
    services/job/matching.py     matched/missing skills + score (70% required, 30% preferred)    (pure code)
    services/job/matcher.py      adapter between Pydantic models and the pure matching code
    services/job/suggestions.py  gaps -> 3-5 honest suggestions (LLM, skipped if nothing is missing)

## The tracker (Phase 4)
    db/session.py                  engine, one session per request (get_db), init_db() creates tables at startup
    db/types.py                    UTCDateTime: SQLite forgets timezones, this puts UTC back
    models/application.py          ORM tables: applications, status_changes, match_snapshots (+ CHECK/FK rules)
    schemas/application.py         API shapes (input rules differ from output shapes; unknown fields rejected)
    services/application_service.py  all the logic; raises Python exceptions, knows nothing about HTTP
    api/applications.py            thin routes

Privacy rule: the database never stores a resume - not the file, not its text, not parsed fields.
A match snapshot keeps only the job description, the score, and skill names. The endpoint rejects
(422) any request that includes extra fields such as "resume".

## The knowledge base (Phase 6) - RAG
Your own notes (project write-ups, STAR stories, achievements) are stored and searched. The resume is
never indexed (Phase 4 privacy rule).

    services/rag/chunker.py          split a note into overlapping chunks (recursive splitter, from scratch)
    services/rag/embedder.py         text -> vector. LocalEmbedder (real model) / HashingEmbedder (word overlap only)
    services/rag/similarity.py       cosine similarity, written by hand
    services/rag/vector_store.py     InMemoryVectorStore: the simplest vector database
    services/rag/chroma_store.py     ChromaVectorStore: same interface, saved to backend/chroma_data
    services/rag/knowledge_service.py  add / list / view / delete / search (no HTTP, no pydantic)
    services/rag/prompts.py          the grounded prompt; sources are numbered [1], [2], ...
    services/rag/citations.py        checks the model's citations (drops invented ones, flags uncited answers)
    services/rag/answerer.py         retrieved chunks -> LLM -> validated answer (reuses generate_structured)

Endpoints: POST/GET/DELETE /knowledge/documents, POST /knowledge/search (no LLM, shows scores),
POST /knowledge/ask (retrieve, then answer; skips the LLM when nothing relevant is found).

Settings (all optional, see .env.example): RAG_EMBEDDER=local|hashing, RAG_STORE=chroma|memory,
RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_MIN_SCORE. Switching the embedder opens a separate collection,
because vectors from different models cannot be compared.

    python -m pytest                                              # everything except the real-model tests
    RUN_LOCAL_MODEL_TESTS=1 python -m pytest tests/test_local_model.py -v -s   # downloads ~80 MB

## The agent (Phase 7)
An agent is a loop: ask the model what to do, run the tool it picked, show it the result, repeat.
Tool calling here is prompt-based JSON (no provider-specific function calling), so it works with any
LLM provider and reuses the structured-output machinery from Phase 2.

    services/agent/loop.py            the loop + its guards (step limit, repeated-call block, wrap-up on the last step)
    services/agent/tools.py           Tool, ToolParam, argument validation, the registry, and execute_tool (never raises)
    services/agent/prompts.py         how the model is told about the tools; how the steps so far are shown
    services/agent/decider.py         asks the LLM for its next Decision (generate_structured + AgentDecision)
    services/agent/knowledge_tools.py search_knowledge        (Phase 6 notes)
    services/agent/tracker_tools.py   list_applications, get_application   (Phase 4 tracker)
    services/agent/builtin_tools.py   the toolbox: add a Tool to the list to give the agent a new ability

Read-only by design: no tool creates, changes or deletes anything (a test enforces it).
Each step is one LLM call, so one question costs about 2-4 calls. AGENT_MAX_STEPS (default 4) caps it.
Tool results are sent to your LLM provider, like any prompt.

## The MCP server (Phase 8)
MCP (Model Context Protocol) is a standard way for AI apps (Claude Desktop, IDE assistants, your own agents)
to discover and call tools in your program. This server is a thin, READ-ONLY adapter: it never touches your
database or Chroma folder; it asks your running backend for data over HTTP.

    mcp_server/api_client.py   HTTP client (standard library only). Allowlist: GET /applications, GET /applications/{id},
                               POST /knowledge/search. Anything else is refused before it is sent.
    mcp_server/tools.py        the tool logic as plain functions + the interview prompt text (testable without the SDK)
    mcp_server/server.py       registers them with the MCP Python SDK v2 (MCPServer): 3 tools, 2 resources, 1 prompt
    run_mcp_server.py          launcher that works from any folder (this is what Claude Desktop runs)

What it offers: tools list_applications, get_application, search_knowledge; resources career://applications and
career://applications/{id}; prompt prepare_for_interview.

Setup (SDK v2; if it conflicts with your other packages, use a separate virtual environment - it needs nothing else):

    pip install -r requirements-mcp.txt
    uvicorn app.main:app                             # the backend must be running
    python -m scripts.mcp_client_demo --application 1   # try it: starts the server over stdio and calls it
    npx @modelcontextprotocol/inspector python run_mcp_server.py    # interactive browser UI

Claude Desktop: add this to claude_desktop_config.json (macOS: ~/Library/Application Support/Claude/,
Windows: %APPDATA%\Claude\), using ABSOLUTE paths, then restart Claude Desktop:

    {
      "mcpServers": {
        "career-copilot": {
          "command": "/ABSOLUTE/PATH/TO/backend/.venv/bin/python",
          "args": ["/ABSOLUTE/PATH/TO/backend/run_mcp_server.py"],
          "env": { "CAREER_COPILOT_API_URL": "http://127.0.0.1:8000" }
        }
      }
    }

(Windows python path: C:\\ABSOLUTE\\PATH\\backend\\.venv\\Scripts\\python.exe)

Settings (environment variables of the MCP process): CAREER_COPILOT_API_URL (default http://127.0.0.1:8000),
CAREER_COPILOT_TIMEOUT (seconds, default 15).

PRIVACY: when an AI app calls these tools, the results (your applications and notes) are sent to that app's
AI provider. Only connect apps you trust with this data. The server is read-only, so a connected app cannot change it.
A stdio server must never print to stdout (it carries the protocol); logs go to stderr.

## Interview preparation (Phase 9)
For one application, generate a pack of likely interview questions, each with an answer outline built ONLY from
your own notes (citing them by title), and an honest "no story found" flag where none of your notes fit.

    POST   /applications/{id}/interview-prep?question_count=8   generate (or regenerate) - 2 LLM calls
    GET    /applications/{id}/interview-prep                    the saved pack, no LLM call
    DELETE /applications/{id}/interview-prep

Needs a saved match on the application (it holds the job description): save one from the Match tool.

    services/interview/pipeline.py    the workflow in plain code; the two LLM steps are injected functions
    services/interview/prompts.py     question prompt (with a computed behavioral/technical/gap mix) and drafting prompt
    services/interview/generators.py  the two LLM steps (generate_structured: JSON, validation, one retry)
    services/interview_service.py     load application -> run workflow -> save (one row per application)
    models/interview_prep.py          the new table (created automatically at startup; no migration needed)

Why a workflow and not the agent: the steps never change, so code guarantees the order, the cost (2 LLM calls,
1 if no note matches anything) and the shape of the result. Quality checks in code: a note can only be cited for a
question it was retrieved for, invented citations are dropped, and an answer that cites no valid note is discarded.
The resume is never used or stored. Setting: INTERVIEW_QUESTION_COUNT (default 8, range 3 to 12).
