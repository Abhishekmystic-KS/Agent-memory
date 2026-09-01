# Bottleneck: Developer Memory Agent

Bottleneck is a local-first memory layer for coding assistants. It helps capture developer preferences, maintain conversation context, and surface useful historical knowledge through a web dashboard.

## Screenshots

![Bottleneck Developer Memory Cockpit](assets/cockpit_dashboard.png)
![Bottleneck Neural Memory Graph](assets/neural_graph_fullscreen.png)

## Memory Architecture

Bottleneck organizes context into four tiers:

1. **Sensory Ingestion Memory**: Captures raw user/agent dialogue and sanitizes risky prompt content.
2. **Short-Term (Working) Memory**: Keeps active conversation context compact with rolling summaries.
3. **Long-Term Episodic Memory**: Stores session history and retrieves it by recency, importance, and relevance.
4. **Long-Term Semantic Memory**: Consolidates structured knowledge and visualizes relationships in the neural graph.

## Core Skills

| Skill | Description |
| --- | --- |
| Prompt Sanitization | Redacts known system-instruction override patterns |
| Contradiction Resolution | Detects conflicting memory entries |
| Decay + YMYL Immunity | Applies decay policies while protecting critical entries |
| Frustration Recovery | Pins memories when reminder cues are detected |
| Codebase Explorer | Provides in-dashboard file browsing and viewing |
| Integration Endpoints | Supports cURL/Python integrations for external agents |

## Quick Start

### 1) Create environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Run the server

```bash
PYTHONPATH=. venv/bin/uvicorn web.server:app --reload
```

### 3) Open the dashboard

Visit: http://127.0.0.1:8000

## API Example

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Project uses FastAPI on port 8000"}'
```

```python
import requests

res = requests.post(
    "http://127.0.0.1:8000/api/chat",
    json={"message": "I prefer PEP 8 and Google-style docstrings"},
)
print(res.json()["reply"])
```

## Run Tests

```bash
PYTHONPATH=. pytest tests/
```

## Project Structure

```text
Agent-memory/
├── bottleneck/          # Core memory modules
│   └── skills/          # Sanitizer, decay, retrieval and related skills
├── web/
│   ├── server.py        # FastAPI backend
│   └── static/          # Frontend assets
├── tests/               # Pytest test suite
└── assets/              # Images and diagrams
```

## License

MIT
