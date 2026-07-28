import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

# ── paths ──────────────────────────────────────────────────────────────
DOCS_DIR      = Path("data/docs")
INCIDENTS_CSV = Path("data/incidents/incidents.csv")
FAISS_DIR     = Path("data/faiss_index")

# ── web sources (scraped live) ──────────────────────────────────────────
WEB_SOURCES = [
    # NERSC
    "https://docs.nersc.gov/jobs/",
    "https://docs.nersc.gov/jobs/troubleshooting/",
    "https://docs.nersc.gov/systems/perlmutter/",
    # SLURM official
    "https://slurm.schedmd.com/quickstart.html",
    "https://slurm.schedmd.com/faq.html",
    "https://slurm.schedmd.com/squeue.html",
    "https://slurm.schedmd.com/scontrol.html",
    "https://slurm.schedmd.com/sbatch.html",
    # Open MPI
    "https://www.open-mpi.org/faq/?category=running",
    "https://www.open-mpi.org/faq/?category=troubleshooting",
    # Princeton HPC
    "https://researchcomputing.princeton.edu/support/knowledge-base/slurm",
    "https://researchcomputing.princeton.edu/support/knowledge-base/mpi",
]

# ── embedding model (runs locally, no API key needed) ───────────────────
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

# ── loaders ─────────────────────────────────────────────────────────────
def load_pdfs() -> list[Document]:
    docs = []
    pdf_files = list(DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        print("  [!] No PDFs found in data/docs/")
        return docs
    for pdf_path in pdf_files:
        print(f"  Loading PDF: {pdf_path.name}")
        try:
            loader = PyPDFLoader(str(pdf_path))
            pages  = loader.load()
            # tag each page with its source file
            for page in pages:
                page.metadata["source_type"] = "pdf"
                page.metadata["source"]      = pdf_path.name
            docs.extend(pages)
            print(f"    → {len(pages)} pages loaded")
        except Exception as e:
            print(f"    [!] Failed to load {pdf_path.name}: {e}")
    return docs


def load_web_sources() -> list[Document]:
    docs = []
    for url in WEB_SOURCES:
        print(f"  Scraping: {url}")
        try:
            loader = WebBaseLoader(url)
            loader.requests_kwargs = {"timeout": 15}
            pages  = loader.load()
            for page in pages:
                page.metadata["source_type"] = "web"
                page.metadata["source"]      = url
            docs.extend(pages)
            print(f"    → {len(pages)} page(s) loaded")
        except Exception as e:
            print(f"    [!] Failed to scrape {url}: {e}")
    return docs


def load_incidents_csv() -> list[Document]:
    docs = []
    if not INCIDENTS_CSV.exists():
        print("  [!] incidents.csv not found")
        return docs
    print(f"  Loading incidents CSV")
    df = pd.read_csv(INCIDENTS_CSV)
    for _, row in df.iterrows():
        # combine all columns into a rich text block
        content = (
            f"ERROR: {row.get('error', '')}\n"
            f"CAUSE: {row.get('cause', '')}\n"
            f"SOLUTION: {row.get('solution', '')}\n"
            f"CATEGORY: {row.get('category', '')}\n"
            f"COMMANDS: {row.get('commands', '')}"
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "source":      "incidents.csv",
                "source_type": "incident",
                "category":    str(row.get("category", "")),
            }
        ))
    print(f"    → {len(docs)} incidents loaded")
    return docs


# ── chunker ─────────────────────────────────────────────────────────────
def chunk_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    # drop empty chunks
    chunks = [c for c in chunks if len(c.page_content.strip()) > 30]
    print(f"\n  Total chunks after splitting: {len(chunks)}")
    return chunks


# ── main ingestion ───────────────────────────────────────────────────────
def ingest():
    print("\n=== HPC RAG Assistant — Ingestion Pipeline ===\n")

    # 1. load all sources
    print("[1/4] Loading documents...")
    all_docs = []
    all_docs.extend(load_pdfs())
    all_docs.extend(load_web_sources())
    all_docs.extend(load_incidents_csv())
    print(f"\n  Total raw documents loaded: {len(all_docs)}")

    if not all_docs:
        print("\n[!] No documents loaded. Check your data/ folder and web sources.")
        return

    # 2. chunk
    print("\n[2/4] Chunking documents...")
    chunks = chunk_documents(all_docs)

    # 3. embed + build FAISS index
    print("\n[3/4] Embedding chunks (this takes a few minutes first time)...")
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # 4. save to disk
    print("\n[4/4] Saving FAISS index to disk...")
    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(FAISS_DIR))
    print(f"\n✅ Done! Index saved to {FAISS_DIR}")
    print(f"   {len(chunks)} chunks indexed and ready.\n")


if __name__ == "__main__":
    ingest()