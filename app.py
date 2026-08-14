import streamlit as st
from rag.pipeline import RAGPipeline

# ── page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HPC Assistant",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS — chat layout ────────────────────────────────────────────────────
st.markdown("""
<style>
/* hide streamlit defaults */
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1rem; padding-bottom: 0rem;}

/* sidebar styling */
[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #2d2d2d;
    width: 280px !important;
}
[data-testid="stSidebar"] .stButton button {
    background: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    text-align: left;
    font-size: 0.82rem;
    padding: 8px 12px;
    width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
    transition: background 0.2s;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #313244;
    border-color: #89b4fa;
}

/* chat message bubbles */
.user-bubble {
    background: #1e3a5f;
    color: #e2e8f0;
    padding: 12px 16px;
    border-radius: 16px 16px 4px 16px;
    margin: 8px 0 8px 15%;
    font-size: 0.95rem;
    line-height: 1.5;
}
.assistant-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 16px 0 8px 0;
    color: #89b4fa;
    font-weight: 600;
    font-size: 0.9rem;
}
.source-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 2px 3px;
}
.badge-incident { background:#2d1b00; color:#fbbf24; border:1px solid #92400e;}
.badge-web      { background:#001a3d; color:#60a5fa; border:1px solid #1e40af;}
.badge-pdf      { background:#002d1a; color:#34d399; border:1px solid #065f46;}
.chunk-expander {
    background: #1a1a2e;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 4px 0;
    font-size: 0.8rem;
    color: #a0aec0;
}
.rewrite-pill {
    background: #1e1e2e;
    border: 1px solid #4a4a6a;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    color: #a0aec0;
    display: inline-block;
    margin-bottom: 12px;
}

/* bottom input bar */
.input-bar {
    position: fixed;
    bottom: 0; left: 280px; right: 0;
    background: #0f1117;
    border-top: 1px solid #2d2d2d;
    padding: 12px 24px;
    z-index: 999;
}

/* push content above fixed input */
.chat-spacer { height: 100px; }

/* answer area */
.answer-wrap {
    background: #13131f;
    border: 1px solid #2d2d2d;
    border-radius: 12px;
    padding: 20px 24px;
    margin: 8px 0 16px 0;
}
</style>
""", unsafe_allow_html=True)

# ── load pipeline ────────────────────────────────────────────────────────
@st.cache_resource
def load_pipeline():
    return RAGPipeline()

# ── session state ─────────────────────────────────────────────────────────
if "chats" not in st.session_state:
    # list of conversations: [{id, title, messages:[{role,content,meta}]}]
    st.session_state.chats = []
if "active_chat" not in st.session_state:
    st.session_state.active_chat = None
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── helpers ───────────────────────────────────────────────────────────────
def new_chat():
    chat_id = len(st.session_state.chats)
    st.session_state.chats.append({
        "id":       chat_id,
        "title":    "New chat",
        "messages": [],
    })
    st.session_state.active_chat = chat_id

def get_active():
    if st.session_state.active_chat is None:
        return None
    return st.session_state.chats[st.session_state.active_chat]

# ── sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🖥️ HPC Assistant")
    if st.button("＋  New chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()

    # chat history list
    if st.session_state.chats:
        st.markdown("**Recent chats**")
        for chat in reversed(st.session_state.chats):
            label = chat["title"][:35] + "…" if len(chat["title"]) > 35 else chat["title"]
            is_active = chat["id"] == st.session_state.active_chat
            btn_label = f"{'▶ ' if is_active else ''}{label}"
            if st.button(btn_label, key=f"chat_{chat['id']}", use_container_width=True):
                st.session_state.active_chat = chat["id"]
                st.rerun()
    else:
        st.caption("No chats yet. Start one above.")

    st.divider()
    st.markdown("**Knowledge base**")
    st.caption("4,010 indexed chunks\n5 PDFs · 12 web pages · 30 incidents")
    st.divider()
    st.markdown("**Try asking:**")
    examples = [
        "SLURM job stuck in PD state",
        "MPI job hangs after launch",
        "Node not responding",
        "Disk quota exceeded",
        "Permission denied on /scratch",
        "OOM kill in SLURM job",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            if st.session_state.active_chat is None:
                new_chat()
            st.session_state.pending_question = ex
            st.rerun()

# ── main area ─────────────────────────────────────────────────────────────
active = get_active()

if active is None:
    # welcome screen
    st.markdown("""
    <div style='text-align:center; margin-top:15vh;'>
        <div style='font-size:3rem;'>🖥️</div>
        <h2 style='color:#89b4fa; margin:8px 0;'>HPC & Linux Troubleshooting Assistant</h2>
        <p style='color:#6b7280; font-size:0.95rem;'>
            Powered by RAG over real NERSC, SLURM, MPI, and Linux documentation
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    cards = [
        ("⚙️", "SLURM Scheduler", "Job pending, OOM kills, walltime, node failures"),
        ("🔗", "MPI Communication", "Job hangs, rank errors, Infiniband issues"),
        ("🐧", "Linux Admin", "Permissions, quota, modules, SSH, NFS"),
    ]
    for col, (icon, title, desc) in zip([col1, col2, col3], cards):
        with col:
            st.markdown(f"""
            <div style='background:#1e1e2e; border:1px solid #2d2d2d; border-radius:12px;
                        padding:20px; text-align:center; cursor:pointer;'>
                <div style='font-size:2rem;'>{icon}</div>
                <div style='color:#cdd6f4; font-weight:600; margin:8px 0;'>{title}</div>
                <div style='color:#6b7280; font-size:0.82rem;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align:center; margin-top:32px; color:#4a5568; font-size:0.85rem;'>
        Click <b>＋ New chat</b> in the sidebar or pick an example to get started
    </div>
    """, unsafe_allow_html=True)

else:
    # ── render existing messages ─────────────────────────────────────────
    for msg in active["messages"]:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-bubble">🧑 {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            # assistant message
            meta = msg.get("meta", {})

            # rewritten query pill
            if meta.get("rewritten_query"):
                st.markdown(
                    f'<div class="rewrite-pill">🔄 Searched for: {meta["rewritten_query"]}</div>',
                    unsafe_allow_html=True,
                )

            # two column layout — answer left, sources right
            ans_col, src_col = st.columns([3, 1])

            with ans_col:
                st.markdown(
                    f'<div class="answer-wrap">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )

            with src_col:
                st.markdown("**Sources**")
                for source in meta.get("sources", []):
                    if "incidents" in source:
                        badge = "badge-incident"
                        label = "📊 Incidents DB"
                    elif source.startswith("http"):
                        domain = source.split("/")[2]
                        badge = "badge-web"
                        label = f"🌐 {domain}"
                    else:
                        badge = "badge-pdf"
                        label = f"📄 {source}"
                    st.markdown(
                        f'<span class="source-badge {badge}">{label}</span>',
                        unsafe_allow_html=True,
                    )

                if meta.get("chunks"):
                    st.markdown("---")
                    st.markdown("**Retrieved chunks**")
                    for i, chunk in enumerate(meta["chunks"], 1):
                        src  = chunk.metadata.get("source", "unknown")
                        stype = chunk.metadata.get("source_type", "").upper()
                        with st.expander(f"Chunk {i} · {stype}"):
                            st.caption(src)
                            st.markdown(chunk.page_content[:400] + "…")

    # ── process pending question ─────────────────────────────────────────
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None

        pipeline = load_pipeline()

        # add user message
        active["messages"].append({"role": "user", "content": question})
        # set chat title from first question
        if active["title"] == "New chat":
            active["title"] = question[:40]

        st.markdown(
            f'<div class="user-bubble">🧑 {question}</div>',
            unsafe_allow_html=True,
        )

        # rewrite + retrieve
        with st.spinner("Searching documentation…"):
            result = pipeline._rewrite_and_retrieve(question)

        st.markdown(
            f'<div class="rewrite-pill">🔄 Searched for: {result["rewritten_query"]}</div>',
            unsafe_allow_html=True,
        )

        # stream answer
        ans_col, src_col = st.columns([3, 1])

        with src_col:
            st.markdown("**Sources**")
            for source in result["sources"]:
                if "incidents" in source:
                    badge, label = "badge-incident", "📊 Incidents DB"
                elif source.startswith("http"):
                    badge  = "badge-web"
                    label  = f"🌐 {source.split('/')[2]}"
                else:
                    badge, label = "badge-pdf", f"📄 {source}"
                st.markdown(
                    f'<span class="source-badge {badge}">{label}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown("---")
            st.markdown("**Retrieved chunks**")
            for i, chunk in enumerate(result["chunks"], 1):
                src   = chunk.metadata.get("source", "unknown")
                stype = chunk.metadata.get("source_type", "").upper()
                with st.expander(f"Chunk {i} · {stype}"):
                    st.caption(src)
                    st.markdown(chunk.page_content[:400] + "…")

        with ans_col:
            stream_box  = st.empty()
            full_answer = ""
            for chunk in pipeline.llm.stream(
                pipeline._build_prompt(result["context"], question)
            ):
                full_answer += chunk.content
                stream_box.markdown(
                    f'<div class="answer-wrap">{full_answer} ▌</div>',
                    unsafe_allow_html=True,
                )
            stream_box.markdown(
                f'<div class="answer-wrap">{full_answer}</div>',
                unsafe_allow_html=True,
            )

        # save to chat history
        active["messages"].append({
            "role":    "assistant",
            "content": full_answer.strip(),
            "meta":    {
                "rewritten_query": result["rewritten_query"],
                "sources":         result["sources"],
                "chunks":          result["chunks"],
            },
        })

    # spacer so content clears the fixed input bar
    st.markdown('<div class="chat-spacer"></div>', unsafe_allow_html=True)

# ── fixed bottom input bar ─────────────────────────────────────────────
with st.container():
    st.markdown('<div class="input-bar">', unsafe_allow_html=True)
    col_input, col_btn = st.columns([9, 1])
    with col_input:
        question_input = st.text_input(
            label="input",
            label_visibility="collapsed",
            placeholder="Describe your HPC or Linux issue…",
            key="main_input",
        )
    with col_btn:
        send = st.button("Send ➤", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if send and question_input.strip():
    if st.session_state.active_chat is None:
        new_chat()
    st.session_state.pending_question = question_input.strip()
    st.rerun()
elif send and not question_input.strip():
    st.warning("Type something first.")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting HPC Assistant Gemini Web Server on http://127.0.0.1:8000 ...\n")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)