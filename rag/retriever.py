import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress verbose third-party logs & deprecation warnings
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    from langchain_classic.retrievers import EnsembleRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

load_dotenv()

FAISS_DIR = Path("data/faiss_index")

# ── embedding model (same as ingestion — must match) ────────────────────
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

# ── load FAISS index from disk ──────────────────────────────────────────
def load_vectorstore():
    if not FAISS_DIR.exists():
        raise FileNotFoundError(
            f"FAISS index not found at {FAISS_DIR}. "
            "Run ingestion first: python -m rag.ingestion"
        )
    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(
        str(FAISS_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    print(f"  [+] FAISS index loaded ({vectorstore.index.ntotal} vectors)")
    return vectorstore

# ── reranker (cross-encoder runs locally) ──────────────────────────────
class Reranker:
    def __init__(self):
        print("  [+] Loading cross-encoder reranker...")
        self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(self, query: str, docs: list[Document], top_k: int = 3) -> list[Document]:
        if not docs:
            return []
        pairs  = [(query, doc.page_content) for doc in docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked[:top_k]]

# ── hybrid retriever (BM25 + FAISS combined) ───────────────────────────
class HybridRetriever:
    def __init__(self, vectorstore, all_docs: list[Document]):
        print("  [+] Building BM25 retriever...")
        bm25_retriever = BM25Retriever.from_documents(all_docs)
        bm25_retriever.k = 10

        print("  [+] Building FAISS retriever...")
        faiss_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10},
        )

        # 50/50 weight between keyword and semantic search
        self.retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, faiss_retriever],
            weights=[0.5, 0.5],
        )
        print("  [+] Hybrid retriever ready")

    def retrieve(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

# ── main retrieval system (combines everything) ─────────────────────────
class RetrievalSystem:
    def __init__(self):
        print("\n[Loading retrieval system...]")
        self.vectorstore = load_vectorstore()

        # get all docs from FAISS for BM25
        all_docs = [
            Document(
                page_content=self.vectorstore.docstore._dict[doc_id].page_content,
                metadata=self.vectorstore.docstore._dict[doc_id].metadata,
            )
            for doc_id in self.vectorstore.index_to_docstore_id.values()
        ]
        self.hybrid = HybridRetriever(self.vectorstore, all_docs)
        self.reranker = Reranker()
        print("[Retrieval system ready]\n")

    def get_relevant_chunks(self, query: str, top_k: int = 3) -> list[Document]:
        # step 1: hybrid search gets top 10
        candidates = self.hybrid.retrieve(query)
        # step 2: reranker cuts to top_k best
        reranked   = self.reranker.rerank(query, candidates, top_k=top_k)
        return reranked


# ── quick test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    system = RetrievalSystem()
    test_query = "why is my SLURM job stuck in PD state"
    print(f"Test query: {test_query}\n")
    results = system.get_relevant_chunks(test_query)
    print(f"Top {len(results)} chunks after reranking:\n")
    for i, doc in enumerate(results, 1):
        print(f"--- Chunk {i} ---")
        print(f"Source: {doc.metadata.get('source', 'unknown')}")
        print(f"Content: {doc.page_content[:300]}")
        print()