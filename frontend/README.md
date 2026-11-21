# AI Career Copilot - frontend (Phase 5)

React + TypeScript + Vite + Tailwind CSS. Talks to the FastAPI backend in `../backend`.

Requires Node 20.19+ or 22.12+ (check with `node --version`).

## Run it

Terminal 1 - backend (from `backend/`, with its virtual environment active):

    uvicorn app.main:app --reload

Terminal 2 - frontend (from `frontend/`):

    npm install
    npm run dev

Open http://localhost:5173

In development, Vite forwards every request that starts with `/api` to the backend on port 8000
(`vite.config.ts`), so the browser only ever talks to one origin and no CORS setup is needed.

## Commands

    npm run dev         start the dev server with hot reload
    npm test            run all tests once (Vitest)
    npm run test:watch  re-run tests as you edit
    npm run typecheck   TypeScript check, no output files
    npm run build       typecheck + production build into dist/
    npm run preview     serve the production build locally

## How it is organised

    src/api/types.ts      TypeScript versions of the backend's Pydantic schemas
    src/api/client.ts     the ONLY file that calls fetch(): one function per endpoint + error handling
    src/lib/              small pure functions (validation, grouping, formatting) - easy to test
    src/hooks/            useApplications: loads the list, exposes reload()
    src/components/       reusable pieces (card, form, detail panel, score bar, ...)
    src/pages/            one page per tab: Tracker, Match, Knowledge (Notes), Agent, Interview
    src/App.tsx           tabs, and the application list loaded once and shared by both pages

Data flow: `App` loads the applications once and passes them down. When the Match tool saves a match
it calls `reload()`, and the Tracker updates because both pages share that same state.

## The tabs
    Tracker          kanban board of your applications: create, edit, move through statuses, delete
    Match tool       upload a resume, paste a job, see the match score and gaps, save the match to an application
    Notes            your own career notes: add, delete, see how each was split into passages, search them (no AI),
                     and ask a question answered ONLY from them, with clickable citations and a "grounded" badge
    Ask the agent    one question; the agent looks things up in your tracker and notes (read-only) and the full
                     trace of its tool calls is shown
    Interview prep   pick an application: likely questions, each with an answer outline built from YOUR notes
                     (cited by title), a clear "No story found" flag where none of your notes fit, and a coverage
                     summary telling you which stories to write. Needs a saved match on the application.

The Notes, Ask the agent and Interview prep tabs are only loaded the first time you open them.

## Privacy

The parsed resume lives only in `MatchPage` component state (browser memory). It is never written to
`localStorage`, never sent to the tracker endpoints, and the "Remove resume" button clears it. To read
it, the backend sends the resume text to the configured AI provider (e.g. Gemini).
