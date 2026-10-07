import re
import json
import dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

dotenv.load_dotenv()

MODEL = "openai/gpt-oss-20b"

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

def chapter_index(chapters):
    return "\n".join(f"{i}. {c['title']}" for i, c in enumerate(chapters))

def subsection_index(chapter):
    return "\n".join(f"{i}. {s['title']}" for i, s in enumerate(chapter["subsections"]))

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

def run(question: str):
    chapters = load_tree("data/nested_manual.md")
    llm = ChatGroq(model=MODEL)

    c_idx = pick(llm, chapter_index(chapters), question)
    chapter = chapters[c_idx]
    print(f"[hop 1] chapter -> {chapter['title']}")

    if chapter["subsections"]:
        s_idx = pick(llm, subsection_index(chapter), question)
        subsection = chapter["subsections"][s_idx]
        print(f"[hop 2] subsection -> {subsection['title']}")
    else:
        subsection = {"title": chapter["title"], "text": chapter["text"]}
        print(f"[hop 2] (no subsections -- using chapter text directly)")

    result = answer(llm, subsection, question)
    print(f"\nAnswer: {result}")
    return result


if __name__ == "__main__":
    test_questions = [
        "How long are user sessions valid for?",
        "What happens if I exceed my API rate limit?",
        "Why does the system use a secondary ranking step after similarity search?",
        "What programming language is the backend written in?",
        "What's the process if someone's session needs to be terminated urgently after a security issue?",
        "What is nested_manual.md",
    ]
    for q in test_questions:
        print(f"Question: {q}")
        run(q)
        print("-" * 50)