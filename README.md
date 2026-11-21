AI Career Copilot

An AI-powered career management platform built with React, TypeScript, FastAPI, SQLite, RAG, AI Agents, and MCP.

Career Copilot helps users manage job applications, analyze job descriptions, match resumes with opportunities, organize career knowledge, and prepare for technical interviews.

Features

- Job Application Tracker: Manage applications through a Kanban-style workflow.
- Resume-to-Job Matching: Analyze resumes against job descriptions and generate match scores and improvement suggestions.
- AI-Powered Job Analysis: Extract skills and requirements from job descriptions.
- RAG Knowledge Base: Store, search, and retrieve personal career notes using semantic search.
- AI Agent: Uses read-only tools to retrieve application and knowledge information before answering questions.
- Interview Preparation: Generate interview questions and answer outlines based on saved job matches and personal notes.
- MCP Integration: Expose read-only career tools through the Model Context Protocol.

Technology Stack

Layer| Technologies
Frontend| React, TypeScript, Vite, Tailwind CSS
Backend| Python, FastAPI
Database| SQLite, SQLAlchemy
AI| Gemini, configurable LLM provider
RAG| Embeddings, vector search, Chroma
Agent| LLM-based tool-calling loop
Integration| Model Context Protocol (MCP)
Testing| Pytest, Vitest

Project Architecture

career-copilot/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── mcp_server/
│   ├── scripts/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── pages/
│   └── README.md
│
├── .gitignore
└── README.md

Development Phases

Phase| Implementation
1| FastAPI foundation and configurable LLM provider
2| Resume parsing and structured extraction
3| Job description analysis and resume matching
4| SQLite-based application tracker
5| React frontend and backend integration
6| RAG-based career knowledge base
7| AI agent with read-only tools
8| MCP server integration
9| Interview preparation workflow

Getting Started

Prerequisites

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+
- npm
- Gemini API key (for AI-powered features)

1. Clone the repository

git clone https://github.com/sibasishsahoo/career-copilot.git
cd career-copilot

2. Configure the backend

cd backend
python -m venv .venv

Activate the environment on Windows:

.\.venv\Scripts\Activate.ps1

Install dependencies:

pip install -r requirements.txt

Copy ".env.example" to ".env" and configure your Gemini API key.

3. Start the backend

From the "backend/" directory:

uvicorn app.main:app --reload

Backend API: "http://127.0.0.1:8000"

Swagger documentation: "http://127.0.0.1:8000/docs"

4. Start the frontend

Open another terminal:

cd frontend
npm install
npm run dev

Frontend: "http://localhost:5173"

Testing

Backend

From the backend directory:

python -m pytest -v

Frontend

From the frontend directory:

npm run test
npm run typecheck
npm run build

Privacy and Security

- Resume files are not stored in the application database.
- Parsed resume data is kept in MatchPage component state (browser memory).
- Career notes are stored and searched separately in the knowledge base.
- The AI agent uses read-only tools and cannot create, modify, or delete application data.
- When AI features are used, relevant information may be sent to the configured AI provider for processing.
- Keep API keys and ".env" files out of version control.

Documentation

For detailed setup instructions and implementation details, see:

- "Backend README" (backend/README.md)
- "Frontend README" (frontend/README.md)

Future Improvements

Potential areas for further development include deployment, authentication, enhanced analytics, and additional AI-powered career workflows.

Author

Sibasish Sahoo

GitHub: https://github.com/sibasishsahoo

---

AI Career Copilot — A project exploring practical applications of AI, RAG, agents, and MCP in career management.
