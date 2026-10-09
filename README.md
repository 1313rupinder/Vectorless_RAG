# Vectorless RAG

**No embeddings. No vector database. The LLM navigates a table of contents instead.**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](YOUR-LIVE-LINK)

**Live demo:** YOUR-LIVE-LINK

A from-scratch implementation of tree-based retrieval-augmented generation, built to understand the idea behind tools like PageIndex, where an LLM reasons its way through a document's structure instead of comparing vector similarity.

<!-- Add a screenshot after you upload it to the repo: ![App screenshot](screenshot.png) -->

## Table of Contents

- [The Idea](#the-idea)
- [Features](#features)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [What Documents Work Best](#what-documents-work-best)
- [Vectorless RAG vs. GraphRAG](#vectorless-rag-vs-graphrag)
- [Known Limitations](#known-limitations)
- [Not the PageIndex Library](#not-the-pageindex-library)
- [Tech Stack](#tech-stack)

## The Idea

Standard RAG converts text into vectors and retrieves by mathematical similarity. That works until similarity and relevance disagree. A contract's warranty-creation clause and its warranty-voiding clause can both score as "similar" to the same query, because they share the same vocabulary. Vector search can't reliably tell them apart.

Vectorless RAG avoids this. Instead of embeddings, it builds a table of contents (chapters containing subsections) and lets the LLM decide which branch answers the question, the way a person flips to a chapter title instead of scanning every page.

```
pick a document
      |
pick a chapter       (LLM reads the chapter titles, picks one)
      |
pick a subsection    (LLM reads that chapter's titles, picks one)
      |
generate the answer  (LLM reads ONLY that subsection's text)
```

Cost per question: up to 4 LLM calls (document, chapter, subsection, answer). Embeddings used: zero.

## Features

- **Chat-style UI:** message bubbles, a pinned input box, a sidebar with chat history, and a New chat button
- **Multi-document support:** navigates across several source files, not just one
- **Two-level tree parsing:** chapters (`#`) containing subsections (`##`)
- **Transparent retrieval:** every answer shows its trail: `document -> chapter -> subsection`
- **Fails safely:** the model is told to say "not found" instead of guessing when a section doesn't contain the answer
- **Input guardrails:** rejects empty questions, questions over 500 characters, and common prompt-injection phrases
- **Index validation:** checks that every choice the navigator makes is a valid entry before using it
- **Fallback for flat chapters:** uses the chapter's own text when it has no subsections, instead of crashing
- **Runs on Groq's free tier:** no OpenAI billing needed

## How It Works

```
disk file (e.g. data/attention_paper.md)
      | open() + read()
one big string
      | split by lines
list of lines
      | classify each line: "# " = chapter, "## " = subsection, else = body text
nested tree: chapters -> subsections -> text      (load_tree(), 0 LLM calls)
      | LLM call: pick a DOCUMENT
one document, parsed into its tree
      | LLM call: pick a CHAPTER from its titles
one chapter
      | LLM call: pick a SUBSECTION (skipped if the chapter has none)
one subsection (with its full text)
      | LLM call: answer using ONLY that text
final answer, shown with the navigation trail
```

| Step | What happens | LLM call? |
|---|---|---|
| Parse | Document split into chapters and subsections using `#` / `##` markers | No |
| Hop 0 | LLM picks which document is relevant | Yes |
| Hop 1 | LLM picks which chapter inside that document | Yes |
| Hop 2 | LLM picks which subsection inside that chapter (skipped if none) | Yes (conditional) |
| Answer | LLM answers using only that subsection's (or chapter's) text | Yes |

The navigator runs at `temperature=0`, so the same question picks the same section every time.

## Project Structure

```
Vectorless_RAG/
|-- app.py                # main app: pipeline + Streamlit chat UI
|-- vectorless_rag.py     # command-line version of the pipeline with test questions
|-- requirements.txt
|-- example.env           # template for your .env file
|-- .gitignore            # keeps .env and the virtual environment out of Git
`-- data/
    |-- nested_manual.md      # sample doc: technical/infra manual
    `-- attention_paper.md    # sample doc: paraphrased "Attention Is All You Need"
```

## Getting Started

**1. Clone and set up the environment**

```bash
git clone https://github.com/1313rupinder/Vectorless_RAG.git
cd Vectorless_RAG
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

**2. Get a free Groq API key** (no credit card required)

1. Sign up at [console.groq.com](https://console.groq.com)
2. Go to API Keys and click Create API Key
3. Copy the key (it starts with `gsk_`)

**3. Set the key**

Either set it in your terminal for the current session (PowerShell):

```powershell
$env:GROQ_API_KEY="gsk_your_key_here"
```

Or copy `example.env` to `.env` and add one line, with no quotes and no spaces around the `=`:

```
GROQ_API_KEY=gsk_your_key_here
```

Never commit your key. `.env` is already in `.gitignore`.

**4. Run it**

```bash
streamlit run app.py
```

It opens in your browser automatically.

## Deployment

The live demo runs on [Streamlit Community Cloud](https://streamlit.io/cloud), deployed from this repo.

1. Push the repo to GitHub (`app.py`, `requirements.txt` and the `data/` folder must be included)
2. On share.streamlit.io, create an app from the repo, branch `main`, main file `app.py`
3. Under Advanced settings, add the key in the Secrets box (TOML format, so the value needs quotes):

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

Streamlit exposes top-level secrets as environment variables, so the app reads the key the same way it does locally.

Free apps go to sleep after a few days without visitors. If the demo shows a sleep screen, click the wake-up button and wait about 30 seconds.

## What Documents Work Best

The technique works on any format, as long as the content has real structure. Structure matters more than format.

| Format | Works well? | Notes |
|---|---|---|
| Markdown (`.md`) | Yes | Headings are plain-text markers (`#`, `##`), so it is the easiest to parse. This is what the project implements. |
| PDF | Yes, with more work | Headings are visual (font size, bold) rather than tagged text, so it needs a layout-aware parser. Not implemented here. |
| DOCX | Yes, with more work | Headings are a paragraph style (e.g. `Heading 1`), so it needs `python-docx` extraction. Not implemented here. |
| Plain `.txt` | Only if structured | Works only if the text uses a consistent heading convention. |
| CSV / tabular data | No | No hierarchy exists to build a tree from. SQL or pandas fit better. |
| Unstructured text (chat logs, scraped pages, raw notes) | Poor fit | No table of contents to reason over. Vector search is the better tool. |

**Does it need hierarchical data? Yes.** This is the one precondition the technique depends on. If a document has no real headings, there are no branches to choose between.

- **Best results:** technical manuals, contracts, financial filings, structured reports, academic papers
- **Poor results:** flat documents, or documents whose headings don't group related content meaningfully

This project hit the failure mode directly: a chapter with no subsections originally crashed the pipeline (`list index out of range`), because the navigator had nothing to pick from. The fix was to fall back to the chapter's own text when it has no subsections.

If your data has no real hierarchy, vector-based RAG is very likely the better tool.

## Vectorless RAG vs. GraphRAG

These solve different-shaped problems.

| | Vectorless RAG | GraphRAG (e.g. Neo4j) |
|---|---|---|
| What it models | Structure within a single document | Relationships between entities across data |
| Retrieval unit | A section of a document | A subgraph of connected nodes |
| Good at | "Which section of this contract covers X?" | Multi-hop questions across linked entities |
| Build step | Parse headings into a tree: cheap, one-time, no LLM needed | LLM extracts entities and relationships, builds a graph: expensive, needs maintenance |
| Query mechanism | LLM reads titles, picks a branch, repeats | Natural language to Cypher query to graph traversal |
| Infrastructure | None: just files and an LLM API | Needs a running graph database |
| Fails on | Documents with no real heading structure | Data with no meaningful entity structure, or when setup cost isn't justified |

A legal contract has hierarchy (chapters, clauses), so vectorless RAG fits. A dataset of people, companies and transactions that reference each other is a network, so GraphRAG fits. Neither replaces plain vector RAG for a large pile of loosely related documents.

**Why vectorless RAG exists at all:** the complaint behind it is narrow. It isn't "we're missing relationship reasoning", it's "vector search retrieves the mathematically similar paragraph instead of the logically correct one" in long, structured documents. That is a chunking and similarity problem, not a missing-graph problem. A table of contents fixes it directly, with no graph database. Using GraphRAG just to find which section of a manual covers refunds would be far more infrastructure than the problem needs.

## Known Limitations

- **No backtracking.** If an early hop picks the wrong branch, the pipeline commits to it. A reproduced example: a question about urgently terminating a session after a security issue was routed to a Monitoring/Incident chapter instead of Authentication, because the navigator matched the question's vocabulary instead of the mechanism being asked about. It failed safely (said "not found") instead of making something up, but it did fail.
- **Structure-dependent.** Only works on documents with real headings.
- **Format-dependent in this implementation.** It parses Markdown `#` / `##` headings only. PDF and DOCX need a different structure-extraction step.
- **Not suited to tabular data.** CSVs have no hierarchy. This is a limit of the technique, not just this code.
- **Two levels only.** Deeper nesting (e.g. `3.2.1`) is flattened into its parent subsection's body text instead of becoming its own navigable node.
- **No conversation memory.** Each question is answered on its own, so a follow-up like "explain that more" won't work. The chat UI shows history but doesn't feed earlier messages to the model.
- **Shared free-tier quota.** The live demo uses one Groq key, so heavy use can hit the free-tier rate limit.

## Not the PageIndex Library

This project does not use PageIndex's API or package. It is an independent, from-scratch implementation of the same underlying idea, built for learning. Real PageIndex can infer a structure even for documents without clean headings, while this implementation needs the headings to already exist in the text. PageIndex also offers a free local mode (`pip install -U pageindex`, using your own LLM key) alongside its paid hosted API. This project's approach is conceptually closest to that local mode.

## Tech Stack

- **LLM:** Groq, `openai/gpt-oss-20b`
- **Orchestration:** LangChain (`langchain-groq`)
- **UI:** Streamlit
- **Vector database:** none, which is the whole point

## License

For educational use. Built as a learning exercise in RAG architectures.
