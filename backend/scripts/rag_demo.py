"""Try the RAG pipeline on the sample notes, step by step, with your real embedding model.

Run from the backend/ folder:

    python -m scripts.rag_demo "How did I reduce deployment time?"
    python -m scripts.rag_demo "Tell me about mentoring" --k 4
    python -m scripts.rag_demo "How did I reduce deployment time?" --ask        # also calls the LLM
    python -m scripts.rag_demo "How did I reduce deployment time?" --chunk-size 200   # see chunking at work

The demo indexes the sample notes into a THROWAWAY in-memory store, so it never touches your real
knowledge base. The first run with RAG_EMBEDDER=local downloads the embedding model (~80 MB).
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.services.llm.base import LLMError
from app.services.llm.factory import get_llm_client
from app.services.rag import knowledge_service as knowledge
from app.services.rag.answerer import answer_question
from app.services.rag.citations import NOT_FOUND_ANSWER
from app.services.rag.errors import RagError
from app.services.rag.factory import build_embedder
from app.services.rag.notes_file import parse_notes
from app.services.rag.vector_store import InMemoryVectorStore

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample_career_notes.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Try RAG on the sample career notes.")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=3, help="how many chunks to retrieve (default 3)")
    parser.add_argument("--chunk-size", type=int, default=None, help="characters per chunk (default from settings)")
    parser.add_argument("--ask", action="store_true", help="also let the LLM answer from the retrieved chunks")
    args = parser.parse_args()

    settings = get_settings()
    chunk_size = args.chunk_size or settings.rag_chunk_size
    overlap = min(settings.rag_chunk_overlap, chunk_size // 4)  # overlap must stay well below chunk_size

    try:
        embedder = build_embedder(settings.rag_embedder)
        min_score = settings.rag_min_score if settings.rag_min_score is not None else embedder.default_min_score
        store = InMemoryVectorStore()

        print(f"Embedder: {embedder.name}   chunk size: {chunk_size}   overlap: {overlap}   cut-off: {min_score}")
        print("\n1. INDEXING the sample notes (chunk -> embed -> store)")
        for title, body in parse_notes(SAMPLE.read_text(encoding="utf-8")):
            info = knowledge.add_document(store, embedder, title, body, chunk_size, overlap)
            print(f"   {info.title!r}: {info.chunk_count} chunk(s)")

        print(f"\n2. RETRIEVING for: {args.question!r}")
        hits = knowledge.search_chunks(store, embedder, args.question, args.k)
        for rank, hit in enumerate(hits, start=1):
            keep = "kept" if hit.score >= min_score else "below the cut-off: /ask would ignore this"
            snippet = " ".join(hit.chunk.text.split())[:90]
            print(f"   [{rank}] score {hit.score:.3f}  {hit.chunk.title}  (chunk {hit.chunk.index})  <{keep}>")
            print(f"       {snippet}...")

        if args.ask:
            usable = [hit for hit in hits if hit.score >= min_score]
            print("\n3. GENERATING an answer from the kept chunks")
            if not usable:
                print(f"   No chunk passed the cut-off, so the LLM is not called.\n   Answer: {NOT_FOUND_ANSWER}")
            else:
                answer = answer_question(get_llm_client(settings), args.question, usable)
                print(f"   Answer: {answer.text}")
                print(f"   Sources used: {answer.sources_used}   grounded: {answer.grounded}")
    except (RagError, LLMError, OSError) as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
