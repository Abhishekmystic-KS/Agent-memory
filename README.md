# Bottleneck: Developer Memory Agent

Bottleneck is an open-source, premium developer memory companion and cognitive architecture layer designed for AI Coding Agents and Copilots (such as Claude Codex). It organizes coding preferences, style guides, project architecture patterns, and codebase environments using a four-tier memory pipeline and an interactive, real-time semantic relation graph.

---

## 🧠 The 4-Tier Developer Memory Architecture

Bottleneck manages developer context through four specialized memory tiers:

1. **Sensory Ingestion Memory**: Captures raw user/agent dialogue and filters input using **Prompt Sanitization** to protect against prompt-injection instructions.
2. **Short-Term (Working) Memory**: Manages the immediate conversation context with rolling token/turn summaries, preventing context window bloat for AI coding assistants.
3. **Long-Term Episodic Memory**: Stores historical session logs. Retrievable memories are weighted using dynamic sliders for **Recency**, **Importance**, and **Relevance**. It supports dynamic decay models and **YMYL (Your Money Your Life) Immunity** to protect sensitive API keys or critical financial/health declarations from decay.
4. **Long-Term Semantic Memory**: Structured knowledge built through consolidation. Whenever the agent "sleeps", it converts unstructured chat history into structured user profiles, codebase parameters, and an **Interactive Force-Directed Node Graph** (powered by vis.js) demonstrating relationships between entities in real-time.

---

## 🔄 Core Cognitive Skills

*   **Prompt Sanitization**: Automatically redacts system instruction override patterns.
*   **Active Contradiction Resolution**: Detects inconsistencies between new user inputs and stored memories, popping up conflict resolution dialogs to update the knowledge state dynamically.
*   **Decay & YMYL Immunity**: Computes memory decay over time (Exponential, Linear, Step) while granting immunity to critical developer configs.
*   **Frustration Recovery**: Monitors user reminders for frustration (e.g. "You forgot that...") to trigger automated fact extraction and high-priority memory pinning.

---

## 🚀 Quick Start

Bottleneck operates **100% offline** (Sandbox Mode) out-of-the-box using local heuristics. You can also supply a Gemini API Key to enable real vector embedding search and LLM-based consolidation.

### 1. Set Up Virtual Environment & Dependencies
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pydantic pytest
```

### 2. Run the Cockpit Server
```bash
PYTHONPATH=. venv/bin/uvicorn web.server:app --reload
```

### 3. Open the Cockpit UI
Navigate to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser.

---

## 🎮 Features to Explore

*   **Developer Chat & System Controls**: Instruct the agent with code context (e.g., "We use Python with black formatting" or "The dev database runs on port 5432").
*   **Interactive Semantic Graph**: Switch to the **Semantic (LTM)** tab to inspect your codebase context rendered as a force-directed layout where nodes (User, Project, Languages) can be dragged, zoomed, and analyzed.
*   **Decay Configurations**: Toggle decay models and observe how retrieval scores update.
*   **Unit Tests**: Validate all memory modules by running `PYTHONPATH=. pytest tests/`.
