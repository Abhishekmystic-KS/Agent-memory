# AetherMemory: AI Agent Memory Playground

AetherMemory is an interactive playground and python framework designed to help you learn how **AI Agent Memory** works. It simulates sensory, short-term, and long-term memory systems, letting you interact with an agent and watch its memory update in real-time.

---

## 🧠 The 4 Tiers of Agent Memory

This project breaks down agent memory into four simple, logical layers:

1. **Sensory Memory:** Captures raw user messages and immediate observations.
2. **Short-Term Memory:** Tracks the active conversation. When chat history gets too long, it automatically summarizes older messages so the agent doesn't run out of token space.
3. **Long-Term Episodic Memory:** Stores all past messages. When you search or chat, it retrieves the most relevant memories by ranking them based on:
   - **Recency:** How recently did the event happen?
   - **Importance:** How crucial is this detail to remember?
   - **Relevance:** Does this match what the user is currently asking?
4. **Long-Term Semantic Memory:** Extracted knowledge. When the agent "sleeps" (consolidates), it extracts structured user profiles (name, interests, location) and builds a relationship graph (e.g., `User` -> `likes` -> `green tea`).

---

## 🚀 Quick Start

AetherMemory works **100% offline** (Sandbox Mode) out-of-the-box. You can also enter a Google Gemini API Key in the UI to enable real AI embedding search and automated reflections.

### 1. Set Up Virtual Environment & Dependencies
Open your terminal in the project directory and run:

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pydantic pytest
```

### 2. Run the Server
Start the backend server:
```bash
PYTHONPATH=. python web/server.py
```

### 3. Open the Playground
Navigate to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser.

---

## 🎮 Features to Try in the Dashboard

* **Chat Panel:** Talk to the agent (e.g. tell it your name, your job, and what you like).
* **Memory Inspector (Right Tab):** Toggle between tabs to watch short-term summaries, episodic history logs, and semantic profile details update.
* **Consolidate (Sleep) Button:** Click this in the header to run the reflection cycle. Watch the raw episodic chat logs transform into structured facts and graph nodes.
* **Retrieval Sliders:** Adjust how much the agent prioritizes recency vs importance vs relevance. Run a search query in the **Retrieval Tester** to see individual scores, and watch matching episodic memories flash green!
* **Run Tests:** You can verify all memory code by running `PYTHONPATH=. pytest tests/` in your terminal.
