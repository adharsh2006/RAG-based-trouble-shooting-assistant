import streamlit as st
from rag.pipeline import RAGPipeline

# ── page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HPC RAG Assistant",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        margin: 2px;
    }
    .badge-incident { background:#fff3cd; color:#856404; }
    .badge-web      { background:#cce5ff; color:#004085; }
    .badge-pdf      { background:#d4edda; color:#155724; }
    .chunk-box {
        background: #f8f9fa;
        border-left: 3px solid #1f77b4;
        padding: 10px 14px;
        border-radius: 4px;
        font-size: 0.82rem;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── load pipeline once (cached so it doesn't reload on every interaction)
@st.cache_resource
def load_pipeline():
    return RAGPipeline()

# ── sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖥️ HPC RAG Assistant")
    st.markdown("**Production-grade troubleshooting for HPC clusters and Linux systems.**")
    st.divider()

    st.markdown("### 📚 Knowledge Base")
    st.markdown("""
- 5 technical PDFs
- 12 live documentation pages
- 30 HPC incident records
- **4,010 indexed chunks**
    """)
    st.divider()

    st.markdown("### ⚙️ Stack")
    st.markdown("""
- LangChain orchestration
- FAISS + BM25 hybrid retrieval
- BGE cross-encoder reranking
- Gemini 1.5 Flash
- LangSmith observability
    """)
    st.divider()

    st.markdown("### 💡 Example Questions")
    examples = [
        "Why is my SLURM job stuck in PD state?",
        "My MPI job hangs after launch",
        "Node not responding in sinfo",
        "Permission denied on /scratch",
        "How do I check disk quota?",
        "SLURM job killed with OOM error",
        "Cannot load shared library at runtime",
        "Infiniband link is down",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex

# ── main area ────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🖥️ HPC & Linux Troubleshooting Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Ask any HPC cluster or Linux system administration question. Powered by RAG over real SLURM, MPI, and Linux documentation.</div>', unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state["history"] = []
if "prefill" not in st.session_state:
    st.session_state["prefill"] = ""

# ── input ─────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
question = st.text_area(
    "Describe your issue:",
    value=prefill,
    height=100,
    placeholder="e.g. Why is my SLURM job stuck in PD state with reason Resources?",
)

col1, col2 = st.columns([1, 5])
with col1:
    submit = st.button("🔍 Diagnose", type="primary", use_container_width=True)
with col2:
    if st.button("🗑️ Clear history", use_container_width=False):
        st.session_state["history"] = []
        st.rerun()

# ── run pipeline ──────────────────────────────────────────────────────────
if submit and question.strip():
    pipeline = load_pipeline()

    # phase 1 — rewrite + retrieve (show spinner)
    with st.spinner("Searching documentation and retrieving relevant chunks..."):
        result = pipeline._rewrite_and_retrieve(question.strip())

    # phase 2 — stream the answer word by word
    st.markdown("### 📋 Diagnosis & Solution")
    stream_box = st.empty()
    full_answer = ""

    for chunk in pipeline.llm.stream(
        pipeline._build_prompt(result["context"], question.strip())
    ):
        full_answer += chunk.content
        stream_box.markdown(full_answer + " ▌")

    stream_box.markdown(full_answer)
    result["answer"] = full_answer.strip()
    st.session_state["history"].append(result)

elif submit and not question.strip():
    st.warning("Please enter a question first.")

# ── display results ───────────────────────────────────────────────────────
for result in reversed(st.session_state["history"]):
    st.divider()

    # question header
    st.markdown(f"### ❓ {result['question']}")

    # rewritten query
    with st.expander("🔄 Rewritten query (used for retrieval)", expanded=False):
        st.code(result["rewritten_query"], language="text")

    # two column layout
    answer_col, source_col = st.columns([2, 1])

    with answer_col:
        st.markdown("### 📋 Diagnosis & Solution")
        st.markdown(result["answer"])

    with source_col:
        st.markdown("### 📎 Sources Used")

        # source badges
        for source in result["sources"]:
            if "incidents" in source:
                badge_class = "badge-incident"
                label = "📊 Incident DB"
            elif source.startswith("http"):
                badge_class = "badge-web"
                label = f"🌐 {source.split('/')[2]}"
            else:
                badge_class = "badge-pdf"
                label = f"📄 {source}"
            st.markdown(
                f'<span class="source-badge {badge_class}">{label}</span>',
                unsafe_allow_html=True,
            )

        st.divider()

        # raw chunks
        st.markdown("**Retrieved chunks:**")
        for i, chunk in enumerate(result["chunks"], 1):
            src = chunk.metadata.get("source", "unknown")
            stype = chunk.metadata.get("source_type", "").upper()
            with st.expander(f"Chunk {i} — {stype}: {src[:40]}"):
                st.markdown(
                    f'<div class="chunk-box">{chunk.page_content[:400]}...</div>',
                    unsafe_allow_html=True,
                )

# ── empty state ───────────────────────────────────────────────────────────
if not st.session_state["history"]:
    st.info("👆 Enter an HPC or Linux issue above and click **Diagnose** to get started.")
    st.markdown("""
    #### What this system can help with:
    | Category | Examples |
    |---|---|
    | SLURM Scheduler | Job pending, OOM kills, walltime exceeded, node failures |
    | MPI Communication | Job hangs, rank errors, Infiniband issues |
    | Linux Administration | Permissions, disk quota, modules, SSH, NFS |
    | HPC Best Practices | Job scripts, memory tuning, process binding |
    """)