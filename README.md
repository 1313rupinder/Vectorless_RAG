# 🌲 Vectorless RAG

**No embeddings. No vector database. The LLM navigates a table of contents instead.**

A from-scratch implementation of tree-based retrieval-augmented generation —
built to understand the mechanism behind tools like [PageIndex](https://pageindex.ai),
where an LLM reasons its way through a document's structure instead of
comparing vector similarity.

---

## 📚 Table of Contents

1. [The Idea](#-the-idea)
2. [What Documents Work Best](#-what-documents-work-best)
3. [Does It Need Hierarchical Data?](#-does-it-need-hierarchical-data)
4. [Vectorless RAG vs. GraphRAG](#-vectorless-rag-vs-graphrag)
5. [Why Vectorless RAG Was Needed at All](#-why-vectorless-rag-was-needed-at-all)
6. [Features](#-features)
7. [Project Structure](#-project-structure)
8. [Getting Started](#-getting-started)
9. [How It Works — Full Pipeline](#-how-it-works--full-pipeline)
10. [Known Limitations](#-known-limitations)
11. [Not the PageIndex Library](#-not-the-pageindex-library)
12. [Tech Stack](#-tech-stack)

---

## 🧠 The Idea

Standard RAG converts text into vectors and retrieves by mathematical
similarity. That works — until similarity and relevance disagree. A
contract's warranty-*creation* clause and its warranty-*voiding* clause can
both score as "similar" to the same query, because they share the same
vocabulary. Vector search can't reliably tell them apart.

**Vectorless RAG sidesteps this entirely.** Instead of embeddings, it builds
a table of contents — chapters containing subsections — and lets the LLM
*reason* about which branch answers the question, the way a person flips to
a chapter title instead of scanning every page.

\`\`\`
📄 pick a document
   ↓
📖 pick a chapter        (LLM reads ~8 titles, picks one)
   ↓
📑 pick a subsection     (LLM reads that chapter's titles, picks one)
   ↓
💬 generate the answer   (LLM reads ONLY that subsection's text)
\`\`\`

**Cost per question: 3 LLM calls. Embeddings used: zero.**

---

## 📄 What Documents Work Best

The technique works on **any document format**, provided the content itself
has real structure. Format is not the deciding factor — structure is.

| Format | Works well? | Notes |
|---|---|---|
| **Markdown (.md)** | ✅ Yes | Headings are plain-text markers (\`#\`, \`##\`) — easiest to parse. What this project currently implements. |
| **PDF** | ✅ Yes | The most common real-world target (contracts, filings, manuals). Headings are visual (font size/bold) rather than tagged text — needs a layout-aware parser, not implemented in this build. |
| **DOCX** | ✅ Yes | Headings are a paragraph *style* (e.g. \`Heading 1\`), not visible text — needs \`python-docx\`-based extraction, not implemented in this build. |
| **Plain .txt** | ✅ Yes, if structured | Only works if the text itself uses a consistent heading convention. |
| **CSV / tabular data** | ❌ No | Fundamentally the wrong shape of data — no hierarchy exists to build a tree from, regardless of implementation. Better suited to SQL/pandas-style querying. |
| **Unstructured text** (chat logs, scraped pages, raw notes) | ❌ Poor fit | No table of contents to reason over. Vector search is the better tool here. |

**This implementation specifically parses Markdown** (\`#\` for chapters, \`##\`
for subsections) because that's the simplest case where structure is
unambiguous. Extending it to PDF/DOCX is a real, valuable next step — the
*technique* supports it, this specific codebase just doesn't parse those
formats yet.

---

## 🏗️ Does It Need Hierarchical Data?

**Yes — this is the single precondition the entire technique depends on.**

Vectorless RAG has nothing to reason over unless the document has genuine
hierarchy: chapters containing subsections, sections containing
sub-sections. The LLM's job at each hop is to read a small set of titles and
pick the one branch worth descending into — if there are no titles, no
structure, and no branches, there's nothing to navigate.

- **Best results:** documents with clear, consistent, meaningful headings —
  technical manuals, contracts, financial filings, structured reports,
  academic papers.
- **Poor results:** flat documents with no heading structure at all, or
  documents where headings exist but don't meaningfully group related
  content (inconsistent structure confuses the navigator as much as no
  structure does).
- **This project confirmed the failure mode directly** — see [Known
  Limitations](#-known-limitations): a chapter with *no* subsections
  originally caused a crash (\`list index out of range\`) because the
  navigator had nothing to pick from. Fixed by falling back to the
  chapter's own text when no subsections exist — but it's a live example of
  how much this technique depends on structure being present and complete.

If your data doesn't have real hierarchy, vector-based RAG (embeddings +
similarity search) is very likely the better tool, not this one.

---

## 🆚 Vectorless RAG vs. GraphRAG

**These are not two competing solutions to the same problem — they solve
different-shaped problems entirely.**

| | Vectorless RAG | GraphRAG (e.g. Neo4j) |
|---|---|---|
| **What it models** | Structure *within* a single document | Relationships *between* entities across data |
| **Retrieval unit** | A section of a document | A subgraph of connected nodes |
| **Good at** | "Which section of this contract covers X?" | "Who did the CEO of the company that acquired X previously work for?" (multi-hop) |
| **Build step** | Parse headings into a tree — cheap, one-time, no LLM needed | LLM extracts entities + relationships, builds a graph — expensive, needs ongoing maintenance |
| **Query mechanism** | LLM reads titles, picks a branch, repeats | Natural language → Cypher query → graph traversal |
| **Infrastructure** | None — just files and an LLM API | Needs a graph database (Neo4j or similar) running |
| **Fails on** | Documents with no real heading structure | Data with no meaningful entity/relationship structure, or when setup cost isn't justified |

A legal contract has **hierarchy** (chapters, clauses) → vectorless RAG
fits. A dataset of people, companies, and transactions that reference each
other has a **network** (entities connected to entities) → GraphRAG fits.
Neither replaces plain vector RAG for "a large pile of loosely related
documents" — that remains the cheapest, most common case for either.

---

## ❓ Why Vectorless RAG Was Needed At All

**Short answer: GraphRAG wasn't replaced — it was never solving this
problem in the first place.**

The confusion is understandable, since both get discussed as "not vector
RAG" alternatives, but the reasoning why each exists is different:

1. **GraphRAG is expensive to build for a problem that doesn't need it.**
   Building a knowledge graph means running an LLM over an entire corpus to
   extract entities and relationships, resolving duplicate entities ("Apple
   Inc." vs. "Apple"), and maintaining that graph as data changes. That's a
   real engineering project. Using it just to answer "which section of this
   200-page manual covers refunds" is a knowledge-graph built to answer a
   table-of-contents lookup — massive overkill.

2. **The actual complaint driving vectorless RAG is narrower.** It isn't
   "we're missing relationship reasoning" — it's "vector search retrieves
   the mathematically similar paragraph instead of the logically correct
   one" in long, structured documents. That's a chunking/similarity
   problem, not a missing-graph problem. A table of contents fixes it
   directly, without needing a graph database at all.

3. **Infrastructure overhead is the practical deciding factor for many
   teams.** GraphRAG needs a running graph database, Cypher query
   generation, and a graph-construction pipeline. Vectorless RAG needs one
   extra LLM call per document, built once. "No new database, no new query
   language" is often the entire pitch.

**If GraphRAG already existed, so did the option to misuse it for problems
it wasn't designed for** — vectorless RAG exists so people don't have to.

---

## ✨ Features

- 🗂️ **Multi-document support** — navigates across multiple source files, not just one
- 🌳 **Two-level tree parsing** — chapters (\`#\`) containing subsections (\`##\`)
- 🔍 **Transparent retrieval** — every answer comes with a visible trail:
  \`document → chapter → subsection\`
- 🛡️ **Fails safely** — explicitly instructed to say *"not found"* rather
  than guess when a section doesn't contain the answer
- 🖥️ **Streamlit UI** — ask questions in a browser, no terminal required
- ⚡ **Runs on Groq's free tier** — no OpenAI billing required
- 🩹 **Handles flat (non-nested) chapters** — falls back to a chapter's own
  text instead of crashing when it has no subsections

---

## 📂 Project Structure

\`\`\`
vectorless_rag/
├── streamlit_app.py       # main app — pipeline + Streamlit UI
├── requirements.txt
├── .env                   # holds GROQ_API_KEY (never commit this)
└── data/
    ├── nested_manual.md       # sample doc: technical/infra manual
    └── attention_paper.md     # sample doc: paraphrased "Attention Is All You Need"
\`\`\`

---

## 🚀 Getting Started

### 1. Clone and set up the environment

\`\`\`bash
git clone <your-repo-url>
cd vectorless_rag
python -m venv venv
venv\\Scripts\\activate        # Windows
pip install -r requirements.txt
\`\`\`

### 2. Get a free Groq API key

No credit card required.

1. Sign up at [console.groq.com](https://console.groq.com)
2. **API Keys → Create API Key**
3. Copy the key (starts with \`gsk_...\`)

### 3. Set the key

\`\`\`powershell
\$env:GROQ_API_KEY="gsk_your_key_here"
\`\`\`

### 4. Run it

\`\`\`bash
streamlit run streamlit_app.py
\`\`\`

Opens automatically in your browser.

---

## 🧩 How It Works — Full Pipeline

\`\`\`
disk file (e.g. data/attention_paper.md)
   │  open() + read()
   ▼
one big string
   │  split by lines
   ▼
list of lines
   │  classify each line: "# " = chapter, "## " = subsection, else = body text
   ▼
nested tree: chapters → subsections → text        (load_tree() — 0 LLM calls)
   │  LLM call: pick a DOCUMENT from the available files
   ▼
one document, parsed into its tree
   │  LLM call: pick a CHAPTER from its titles
   ▼
one chapter (with its subsections, or its own flat text if none exist)
   │  LLM call: pick a SUBSECTION from that chapter's titles (skipped if none exist)
   ▼
one subsection (with its full text)
   │  LLM call: answer using ONLY that text
   ▼
final answer, shown with the full navigation trail
\`\`\`

| Step | What happens | LLM call? |
|---|---|---|
| **Parse** | Document split into chapters → subsections using \`#\` / \`##\` markers | ❌ |
| **Hop 0** | LLM picks which *document* is relevant | ✅ |
| **Hop 1** | LLM picks which *chapter* inside that document | ✅ |
| **Hop 2** | LLM picks which *subsection* inside that chapter (skipped if the chapter has none) | ✅ (conditional) |
| **Answer** | LLM answers using **only** that subsection's (or chapter's) text | ✅ |

---

## ⚠️ Known Limitations

- **No backtracking.** If an early hop picks the wrong branch, the pipeline
  commits to it rather than retrying a different path. A real, reproduced
  example: a question about "urgently terminating a session after a
  security issue" was routed to a Monitoring/Incident chapter instead of
  Authentication, because the navigator matched question *vocabulary*
  rather than the actual *mechanism* being asked about. It failed safely
  (said "not found") rather than hallucinating — but it did fail.
- **Structure-dependent.** Only works on documents with real headings.
  Unstructured text (chat logs, scraped pages) has nothing to navigate.
- **Format-dependent (for this implementation).** Parses Markdown \`#\`/\`##\`
  headings specifically. The *technique* works well on PDF/DOCX too — those
  formats just need a different structure-extraction step than this code
  currently implements.
- **Not suited to tabular data.** CSVs have no hierarchy — this is a
  limitation of the technique itself, not just this implementation.
- **Two levels only.** Deeper nesting (e.g. \`3.2.1\`) gets flattened into its
  parent subsection's body text rather than becoming its own navigable node.
- **Flat chapters need a fallback.** A chapter with zero \`##\` subsections
  originally crashed the pipeline (empty list, nothing to pick from) — fixed
  by capturing the chapter's own body text and using it directly when no
  subsections exist.

---

## 🆚 Not the PageIndex Library

This project does **not** use [PageIndex](https://pageindex.ai)'s API or
package — it's an independent, from-scratch implementation of the same
underlying idea, built for learning. Notably, real PageIndex can *infer* a
structure even for documents without clean headings; this implementation
requires the headings to already exist in the text. PageIndex also offers a
free local mode (\`pip install -U pageindex\`, using your own LLM key, no
cloud) alongside its paid hosted API — this project's approach is
conceptually closest to that local mode.

---

## 🛠️ Tech Stack

- **LLM:** [Groq](https://groq.com) — \`openai/gpt-oss-20b\`
- **Orchestration:** LangChain (\`langchain-groq\`)
- **UI:** Streamlit
- **Vector database:** none — that's the whole point 🙂

---

## 📄 License

For educational use — built as a learning exercise in RAG architectures.
