import os
import re
import json
import dotenv
import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
    
dotenv.load_dotenv(override=True)

MODEL = "openai/gpt-oss-20b"
DOCS = {
    "nested_manual.md": "data/nested_manual.md",
    "attention_paper.md": "data/attention_paper.md",
}

# ============================================================
# GUARDRAILS
# ============================================================

def input_guardrail(question: str) -> tuple[bool, str]:
    if not question or not question.strip():
        return False, "Question cannot be empty."

    question = question.strip()

    if len(question) > 500:
        return False, "Question is too long. Please keep it under 500 characters."

    blocked_patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?instructions",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"show\s+(me\s+)?your\s+system\s+prompt",
        r"reveal\s+your\s+instructions",
        r"forget\s+(all\s+)?previous\s+instructions",
    ]

    for pattern in blocked_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return False, "The request contains a blocked instruction pattern."

    return True, ""


def validate_index(index: int, items: list, item_type: str) -> int:
    if not isinstance(index, int):
        raise ValueError(
            f"{item_type} selection must be an integer."
        )

    if index < 0 or index >= len(items):
        raise ValueError(
            f"Invalid {item_type} selection: {index}. "
            f"Valid range is 0-{len(items) - 1}."
        )
    return index

def get_llm():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY is not set. Set it in your terminal before running "
                  "streamlit ($env:GROQ_API_KEY=\"gsk_...\"), or add it to a .env "
                  "file loaded with python-dotenv.")
        st.stop()
    return ChatGroq(model=MODEL, api_key=api_key, temperature=0)


def load_tree(path: str):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    chapters = []
    current_chapter = None
    current_sub = None

    for line in raw.split("\n"):
        if line.startswith("# "):
            current_chapter = {"title": line[2:].strip(), "subsections": [], "text": ""}
            chapters.append(current_chapter)
            current_sub = None

        elif line.startswith("## "):
            current_sub = {"title": line[3:].strip(), "text": ""}
            current_chapter["subsections"].append(current_sub)

        else:
            if current_sub is not None:
                current_sub["text"] += line + "\n"
            elif current_chapter is not None:
                current_chapter["text"] += line + "\n"

    for chapter in chapters:
        chapter["text"] = chapter["text"].strip()
        for sub in chapter["subsections"]:
            sub["text"] = sub["text"].strip()

    return chapters


def doc_index():
    return "\n".join(f"{i}. {name}" for i, name in enumerate(DOCS.keys()))


def chapter_index(chapters):
    return "\n".join(f"{i}. {c['title']}" for i, c in enumerate(chapters))


def subsection_index(chapter):
    return "\n".join(f"{i}. {s['title']}" for i, s in enumerate(chapter["subsections"]))


PICK_PROMPT = """You are navigating a table of contents.
Given the user's question, pick the ONE entry most likely to contain the answer.

Entries:
{index}

Question: {question}

Reply with ONLY a JSON object: {{"choice": <int>}}
"""


def pick(llm, index: str, question: str) -> int:
    prompt = PICK_PROMPT.format(index=index, question=question)
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = re.sub(r"^```json|```$", "", response.content.strip(), flags=re.MULTILINE).strip()
    try:
        return int(json.loads(raw)["choice"])
    except (json.JSONDecodeError, KeyError, ValueError):
        raise RuntimeError(f"Navigator returned something unparseable: {raw!r}")


ANSWER_PROMPT = """Answer the question using ONLY the section below.
If the section does not contain the answer, say so -- do not guess.

Section: {title}
---
{text}
---

Question: {question}
"""


def answer(llm, subsection: dict, question: str) -> str:
    prompt = ANSWER_PROMPT.format(title=subsection["title"], text=subsection["text"], question=question)
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()


def run_pipeline(llm, question: str) -> dict:
    doc_names = list(DOCS.keys())
    d_idx = pick(llm, doc_index(), question)
    d_idx = validate_index( d_idx, doc_names, "document")
    doc_name = doc_names[d_idx]
    doc_path = DOCS[doc_name]

    chapters = load_tree(doc_path)

    c_idx = pick(llm, chapter_index(chapters), question)
    c_idx = validate_index(c_idx, chapters, "chapter")
    chapter = chapters[c_idx]

    if chapter["subsections"]:
        s_idx = pick(llm, subsection_index(chapter), question)
        s_idx = validate_index(s_idx, chapter["subsections"], "subsection")
        subsection = chapter["subsections"][s_idx]
    else:
        subsection = {"title": chapter["title"], "text": chapter["text"]}

    result = answer(llm, subsection, question)

    return {
        "hop0_document": doc_name,
        "hop1_chapter": chapter["title"],
        "hop2_subsection": subsection["title"],
        "answer": result,
    }

st.set_page_config(page_title="Vectorless RAG", page_icon="🔎", layout="centered")

st.markdown(
    """
<style>
[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    border: none;
    box-shadow: none;
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    padding: 0.45rem 0.6rem;
}
[data-testid="stSidebar"] .stButton > button > div {
    justify-content: flex-start;
    width: 100%;
}
[data-testid="stSidebar"] .stButton > button p {
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.08);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
    background: rgba(255, 255, 255, 0.14);
    color: inherit;
}
</style>
""",
    unsafe_allow_html=True,
)

if "chats" not in st.session_state:
    st.session_state.chats = {}
    st.session_state.current = None
    st.session_state.next_id = 1

with st.sidebar:
    if st.button("➕  New chat"):
        st.session_state.current = None
        st.rerun()
    st.markdown("**Chats**")
    if not st.session_state.chats:
        st.caption("No chats yet.")
    for cid in reversed(list(st.session_state.chats)):
        title = st.session_state.chats[cid]["title"]
        label = title if len(title) <= 30 else title[:30] + "..."
        is_open = cid == st.session_state.current
        if st.button(label, key=f"chat_{cid}", type="primary" if is_open else "secondary"):
            st.session_state.current = cid
            st.rerun()

st.title("Vectorless RAG")
st.caption("No embeddings. No vector DB. The LLM navigates a table of contents instead.")

with st.expander("How it works"):
    st.markdown(
        "1. The model picks a **document**\n"
        "2. Then a **chapter**\n"
        "3. Then a **subsection**\n"
        "4. It answers using **only** that section"
    )

current = st.session_state.current
messages = st.session_state.chats[current]["messages"] if current else []

for msg in messages:
    with st.chat_message(msg["role"]):
        if msg.get("trail"):
            st.markdown(msg["trail"])
        st.markdown(msg["content"])

question = st.chat_input("Ask something about the manual or the paper...")

if question:
    if st.session_state.current is None:
        cid = st.session_state.next_id
        st.session_state.next_id += 1
        st.session_state.chats[cid] = {"title": question, "messages": []}
        st.session_state.current = cid

    chat = st.session_state.chats[st.session_state.current]
    chat["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    trail = None
    allowed, reason = input_guardrail(question)
    if not allowed:
        content = f"Request blocked: {reason}"
    else:
        llm = get_llm()
        with st.spinner("Navigating..."):
            try:
                result = run_pipeline(llm, question)
                content = result["answer"]
                trail = (
                    f"`{result['hop0_document']}` → "
                    f"`{result['hop1_chapter']}` → "
                    f"`{result['hop2_subsection']}`"
                )
            except Exception as e:
                content = f"Error: {e}"

    chat["messages"].append({"role": "assistant", "content": content, "trail": trail})
    st.rerun()