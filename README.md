# AetherMemory: Interactive Agent Memory Playground

AetherMemory is an educational framework and interactive visual playground designed to teach and demonstrate the key concepts of **AI Agent Memory Architectures**. Large Language Models (LLMs) are inherently stateless; Agent Memory systems provide the persistent, structured continuity required for agents to learn, adapt, and recall details across multiple interactions.

This project implements a complete multi-tier memory system with a premium, glassmorphic dark-mode dashboard interface that shows memory updates, retrieval weights ranking, and consolidation reports in real-time.

---

## 🧠 Memory Architecture Design

AetherMemory is modeled after cognitive architectures (such as the CoALA framework and the Stanford Generative Agents study), splitting memory into volatile and persistent layers:

```
                  ┌───────────────────────┐
                  │     Sensory Input     │
                  └───────────┬───────────┘
                              │
                              ▼
               ┌─────────────────────────────┐
               │  Short-Term Memory Buffer   ├─────────┐
               │    (Active Conversation)    │         │
               └──────────────┬──────────────┘         │
                              │                  (Every Turn)
                     (Limits Exceeded)                 │
                              │                        ▼
                              ▼               ┌─────────────────┐
                      ┌───────────────┐       │  Episodic Stream│
                      │Rolling Summary│       │ (LTM - Events)  │
                      └───────────────┘       └────────┬────────┘
                                                       │
                                              (Sleep/Consolidate)
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │ Semantic Store  │
                                              │ (LTM - Profile) │
                                              └─────────────────┘
```

### 1. Sensory Memory (`sensory.py`)
The immediate, volatile perception layer. It captures raw, incoming observations and targets the active sub-goal before any filtering or storage occurs.

### 2. Short-Term Memory / Working Memory (`short_term.py`)
Manages the active dialogue context. To prevent context window overflow:
* **Dialogue Buffer:** Keeps a sliding window of the last $N$ turns.
* **Rolling Summarizer:** Once token or turn limits are exceeded, older messages are compressed into a rolling summary context, which is prefixed to subsequent prompts.

### 3. Long-Term Episodic Memory (`episodic.py`)
A searchable database of all past experiences. Retrieval utilizes the Stanford Generative Agents formula to rank memories dynamically:
$$\text{Score} = w_{\text{recency}} \cdot S_{\text{recency}} + w_{\text{importance}} \cdot S_{\text{importance}} + w_{\text{relevance}} \cdot S_{\text{relevance}}$$

* **Recency ($S_{\text{recency}}$):** Modeled as an exponential decay $e^{-\lambda \cdot \Delta t}$ based on time elapsed since the memory was written.
* **Importance ($S_{\text{importance}}$):** An integer score (1-10) indicating how critical the memory is (heuristic or LLM-judged).
* **Relevance ($S_{\text{relevance}}$):** Vector cosine similarity (TF-IDF bag-of-words locally, or Gemini Embeddings online) between the search query and the memory content.

### 4. Long-Term Semantic Memory (`semantic.py`)
Consolidated, generalized knowledge. It consists of:
* **User Profile:** Key-value attributes (e.g., name, location, occupation).
* **Consolidated Facts:** A list of generalized, non-redundant factual statements.
* **Entity Relation Graph:** A conceptual graph structure linking concepts together via directional edges (e.g., `User` --`likes`--> `green tea`).

### 5. Memory Consolidation (`consolidation.py`)
The **Sleep/Reflect Cycle**. Periodically (or via manual trigger), the agent "sleeps" to analyze its episodic memories. It extracts profile attributes, updates relationships, merges facts, and resolves conflicts (e.g. if the user says they now hate coffee, it updates the profile to override the old "likes coffee" preference).

### 6. Evaluation Module (`evaluator.py`)
Measures memory performance metrics:
* **Retrieval Recall & Precision:** Evaluates how accurately the retrieval engine returned relevant memories compared to keyword-similarity ground truths.
* **Compression Ratio:** Computes the prompt footprint savings achieved by the short-term summarizer.

---

## 🛠️ Project Structure

```text
├── aether_memory/               # Core Memory Modules
│   ├── __init__.py
│   ├── sensory.py               # Volatile input buffer
│   ├── short_term.py            # Dialogue buffer & summaries
│   ├── episodic.py              # Experience stream & hybrid search
│   ├── semantic.py              # Profile database & entity graph
│   ├── consolidation.py         # Sleep reflection engine
│   └── evaluator.py             # Evaluation metrics calculations
├── web/
│   ├── server.py                # FastAPI backend endpoints
│   └── static/                  # Glassmorphic Frontend Client
│       ├── index.html           # 3-Column dashboard layout
│       ├── style.css            # Dark gradients & animations
│       └── app.js               # Frontend controller & UI state
├── tests/
│   └── test_memory.py           # Automated unit tests
├── requirements.txt             # Project dependencies
└── README.md                    # Documentation
```

---

## 🚀 Getting Started

AetherMemory runs in two modes out-of-the-box:
1. **Local Sandbox Mode (Default):** Runs 100% locally with zero external keys. Uses local bag-of-words similarity and regex heuristic parser.
2. **Gemini API Mode:** Uses Google Gemini API keys to generate real text embeddings, score memory importance, and generate rich semantic consolidations.

### 1. Set Up Virtual Environment
Create a Python virtual environment to manage dependencies locally:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install fastapi uvicorn pydantic pytest
```

### 3. Run Automated Tests
Verify all memory modules are functioning correctly:
```bash
PYTHONPATH=. pytest tests/
```

### 4. Start the Application Server
Run the FastAPI application from the project root:
```bash
PYTHONPATH=. python web/server.py
```
Open your browser and navigate to **`http://127.0.0.1:8000`** to access the interactive dashboard.

---

## 🎨 Interface Walkthrough

* **Column 1: Controller & Settings:** Tune $w_{\text{recency}}$, $w_{\text{importance}}$, and $w_{\text{relevance}}$ sliders. Perform instant search queries inside the **Retrieval Tester** to see detailed score breakdowns.
* **Column 2: Conversational Dialogue:** Message the agent to write experiences to the episodic memory stream.
* **Column 3: Memory Tiers Inspector:**
  * **Working Memory tab:** Watch system instructions and the rolling summary context updates.
  * **Episodic tab:** View stored experiences. Cards will **glowing flash** in green when retrieved by your chat query!
  * **Semantic tab:** View extracted user profiles, consolidated facts list, and the visual entity-relationship links.
* **Sleep/Consolidate button (Header):** Click to trigger the reflection cycle and watch raw episodic logs translate into structured profile fields and relation cards.
