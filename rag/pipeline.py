import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from rag.retriever import RetrievalSystem
from rag.prompts import QUERY_REWRITER_PROMPT, RAG_PROMPT

load_dotenv()

# ── Gemini LLM ──────────────────────────────────────────────────────────
def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.2,
    )

# ── query rewriter ──────────────────────────────────────────────────────
def rewrite_query(llm, question: str) -> str:
    prompt = QUERY_REWRITER_PROMPT.format(question=question)
    response = llm.invoke(prompt)
    rewritten = response.content.strip()
    print(f"  Original : {question}")
    print(f"  Rewritten: {rewritten}")
    return rewritten

# ── context builder ─────────────────────────────────────────────────────
def build_context(docs: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        source_type = doc.metadata.get("source_type", "")
        parts.append(
            f"[Source {i} — {source_type.upper()}: {source}]\n"
            f"{doc.page_content.strip()}"
        )
    return "\n\n---\n\n".join(parts)

# ── full RAG pipeline ───────────────────────────────────────────────────
class RAGPipeline:
    def __init__(self):
        print("\n[Initialising RAG Pipeline...]")
        self.llm = get_llm()
        self.retrieval = RetrievalSystem()
        print("[RAG Pipeline ready]\n")

    def _rewrite_and_retrieve(self, question: str) -> dict:
        """Runs everything except final generation — used by streaming UI."""
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}")

        # step 1 — rewrite
        print("\n[Step 1] Rewriting query...")
        rewritten = rewrite_query(self.llm, question)

        # step 2 — retrieve
        print("\n[Step 2] Retrieving chunks...")
        docs = self.retrieval.get_relevant_chunks(rewritten)
        print(f"  Retrieved {len(docs)} chunks after reranking")
        for i, doc in enumerate(docs, 1):
            print(f"  Chunk {i}: {doc.metadata.get('source', 'unknown')}")

        # step 3 — build context
        context = build_context(docs)
        sources = list({doc.metadata.get("source", "unknown") for doc in docs})

        return {
            "question":        question,
            "rewritten_query": rewritten,
            "context":         context,
            "sources":         sources,
            "chunks":          docs,
            "answer":          "",
        }

    def _build_prompt(self, context: str, question: str) -> str:
        """Builds the final prompt for Gemini."""
        return RAG_PROMPT.format(context=context, question=question)

    def run(self, question: str) -> dict:
        """Non-streaming run — used for terminal testing."""
        result = self._rewrite_and_retrieve(question)
        print("\n[Step 3] Generating answer with Gemini...")
        prompt  = self._build_prompt(result["context"], question)
        answer  = ""
        for chunk in self.llm.stream(prompt):
            answer += chunk.content
        result["answer"] = answer.strip()
        return result

# ── quick test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = RAGPipeline()

    test_questions = [
        "Why is my SLURM job stuck in PD state?",
        "My MPI job hangs after launch, what should I check?",
        "How do I check disk quota on a Linux HPC system?",
    ]

    for question in test_questions:
        result = pipeline.run(question)
        print(f"\n{'='*60}")
        print("ANSWER:")
        print(result["answer"])
        print(f"\nSOURCES USED: {result['sources']}")
        print(f"{'='*60}\n")