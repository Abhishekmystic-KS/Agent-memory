import os
import time
import re
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from bottleneck.sensory import SensoryMemory
from bottleneck.short_term import ShortTermMemory
from bottleneck.episodic import EpisodicMemory
from bottleneck.semantic import SemanticMemory
from bottleneck.consolidation import MemoryConsolidator, HAS_GEMINI
from bottleneck.evaluator import MemoryEvaluator
from bottleneck.skills import (
    sanitize,
    classify_ymyl_detailed,
    assess_confidence,
    detect_frustration,
    build_uncertainty_guidance,
    build_frustration_response,
    ActiveRetrieval
)

app = FastAPI(title="Bottleneck Memory Agent Backend")

# In-memory agent state
class AgentHarness:
    def __init__(self):
        self.sensory = SensoryMemory()
        self.short_term = ShortTermMemory(max_tokens=1500, max_turns=6)
        self.episodic = EpisodicMemory(decay_rate=0.005)
        self.semantic = SemanticMemory()
        self.consolidator = MemoryConsolidator()
        self.active_retriever = ActiveRetrieval()
        
        # Configuration
        self.w_recency = 1.0
        self.w_importance = 1.0
        self.w_relevance = 1.0
        self.gemini_api_key: Optional[str] = None
        self.total_raw_tokens = 0  # To measure compression
        
        # Advanced Memory Skills Settings
        self.decay_function = "exponential"
        self.uncertainty_mode = "helpful"
        self.ymyl_enabled = True
        
    def clear_all(self):
        self.sensory.clear()
        self.short_term.clear()
        self.episodic.clear()
        self.semantic.clear()
        self.total_raw_tokens = 0
        self.decay_function = "exponential"
        self.uncertainty_mode = "helpful"
        self.ymyl_enabled = True

agent = AgentHarness()

# Pydantic models for API
class ChatMessage(BaseModel):
    message: str

class ConfigUpdate(BaseModel):
    w_recency: float
    w_importance: float
    w_relevance: float
    gemini_api_key: Optional[str] = None
    decay_function: Optional[str] = None
    uncertainty_mode: Optional[str] = None
    ymyl_enabled: Optional[bool] = None

class ConflictResolution(BaseModel):
    memory_id: int
    new_fact: str
    resolution: str  # "keep_new", "keep_old"

class DeleteMemoryRequest(BaseModel):
    memory_type: str  # "episodic", "fact", "profile"
    target_id: Optional[int] = None
    target_text: Optional[str] = None
    target_key: Optional[str] = None

# API Endpoints
@app.post("/api/chat")
async def chat_endpoint(payload: ChatMessage):
    raw_user_msg = payload.message.strip()
    if not raw_user_msg:
        raise HTTPException(status_code=400, detail="Empty message")

    # 1. Prompt Ingestion Sanitization
    user_msg, sanitized_categories = sanitize(raw_user_msg)
    sanitization_info = None
    if sanitized_categories:
        sanitization_info = {
            "original": raw_user_msg,
            "redacted": user_msg,
            "categories": sanitized_categories
        }

    # 2. Update Sensory memory
    agent.sensory.update(raw_input=user_msg, active_goal="Respond to user message")

    # Track raw input tokens
    msg_tokens = agent.short_term._estimate_tokens(user_msg)
    agent.total_raw_tokens += msg_tokens

    # 3. Retrieve relevant episodes from Long-Term Episodic Memory
    query_embedding = None
    if agent.gemini_api_key and HAS_GEMINI:
        try:
            import google.generativeai as genai
            genai.configure(api_key=agent.gemini_api_key)
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=user_msg,
                task_type="retrieval_query"
            )
            query_embedding = result['embedding']
        except Exception as e:
            print(f"Error fetching embedding from Gemini: {e}")

    retrieved = agent.episodic.retrieve(
        query=user_msg,
        query_embedding=query_embedding,
        w_recency=agent.w_recency,
        w_importance=agent.w_importance,
        w_relevance=agent.w_relevance,
        top_k=3,
        decay_function=agent.decay_function
    )

    # 4. Uncertainty & Confidence Assessment
    confidence = assess_confidence(retrieved)
    uncertainty_guidance = build_uncertainty_guidance(confidence, agent.uncertainty_mode, retrieved)

    # 5. Frustration Detection & Recovery
    frustration_reply = None
    if detect_frustration(user_msg):
        frust_response = build_frustration_response(user_msg, confidence, agent.uncertainty_mode)
        if frust_response:
            if frust_response.get("action") == "recover_and_pin":
                pin_fact = frust_response.get("pin_fact")
                if pin_fact:
                    # Classify YMYL for pinning
                    ymyl_res = classify_ymyl_detailed(pin_fact)
                    ymyl_cat = ymyl_res.category
                    decay_immune = ymyl_res.is_strong or (ymyl_res.is_ymyl and agent.ymyl_enabled)
                    
                    # Pin fact to episodic memory
                    agent.episodic.add_memory(
                        content=pin_fact,
                        importance=9,
                        ymyl_category=ymyl_cat,
                        decay_immune=decay_immune
                    )
                frustration_reply = frust_response.get("message")
            elif frust_response.get("action") == "apologize_and_ask":
                frustration_reply = frust_response.get("message")

    # Extract clean text from retrieved memories
    retrieved_texts = [r["memory"]["content"] for r in retrieved]

    # 6. Active Retrieval / Contradiction Detection
    # Update active retriever API Key
    agent.active_retriever.set_api_key(agent.gemini_api_key)
    conflicts = agent.active_retriever.detect_conflicts(user_msg, retrieved)
    active_clarifications = [c.to_dict() for c in conflicts]

    # 7. Formulate the response
    assistant_reply = ""
    importance_rating = 5  # Default importance
    ymyl_category = None
    decay_immune = False

    # Check YMYL Classification
    ymyl_res = classify_ymyl_detailed(user_msg)
    if agent.ymyl_enabled and ymyl_res.is_ymyl:
        ymyl_category = ymyl_res.category
        if ymyl_res.is_strong:
            importance_rating = 8
            decay_immune = True
        else:
            importance_rating = 6
            decay_immune = False

    # If frustration was handled, return that reply
    if frustration_reply:
        assistant_reply = frustration_reply
    # If active retrieval found a conflict, override reply to warn/ask user
    elif conflicts:
        assistant_reply = f"Hold on! {conflicts[0].question}"
    else:
        # Normal chat generation (Gemini or Mock)
        if agent.gemini_api_key and HAS_GEMINI:
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Format the grounding context
                grounding_context = ""
                if retrieved_texts:
                    grounding_context += "\n[RETRIEVED EPISODIC MEMORIES]\n" + "\n".join(f"- {t}" for t in retrieved_texts)
                if agent.semantic.profile:
                    grounding_context += "\n[USER PROFILE]\n" + "\n".join(f"{k}: {v}" for k, v in agent.semantic.profile.items())
                if agent.semantic.facts:
                    grounding_context += "\n[CONSOLIDATED FACTS]\n" + "\n".join(f"- {f}" for f in agent.semantic.facts)
                
                # Construct short-term message payload
                prompt_messages = []
                prompt_messages.append({"role": "system", "content": agent.short_term.system_instruction})
                if grounding_context:
                    prompt_messages.append({
                        "role": "system",
                        "content": f"Use the following retrieved memories and profile details to ground your answers. Do not make up facts if they contradict memory.\n{grounding_context}"
                    })
                
                # Add short term history
                for m in agent.short_term.get_working_context():
                    if m["role"] != "system":
                        prompt_messages.append(m)
                
                prompt_messages.append({"role": "user", "content": user_msg})
                
                # Call Gemini
                combined_prompt = ""
                for msg in prompt_messages:
                    combined_prompt += f"{msg['role'].upper()}: {msg['content']}\n\n"
                combined_prompt += "ASSISTANT:"

                response = model.generate_content(combined_prompt)
                assistant_reply = response.text.strip()

                # Estimate importance rating using Gemini if not already boosted by YMYL
                if importance_rating < 8:
                    imp_prompt = f"Rate the personal or informational importance of this user message from 1 to 10 (where 10 is crucial personal facts or permanent preferences, 1 is small talk/greetings). Return ONLY a single integer digit:\nUser: {user_msg}"
                    imp_res = model.generate_content(imp_prompt).text.strip()
                    try:
                        importance_rating = int(re.search(r'\d+', imp_res).group())
                    except:
                        pass
            except Exception as e:
                print(f"Gemini response generation failed: {e}")
                assistant_reply = f"Error in Gemini Mode: {e}. Falling back to Mock responses."
                agent.gemini_api_key = None  # Reset key or fallback

        # Heuristic/Mock response generation if not using Gemini
        if not assistant_reply:
            if importance_rating < 8:
                # Rate importance heuristically
                importance_rating = 2
                important_keywords = ["name", "live", "work", "job", "study", "code", "favorite", "like", "dislike", "hate", "remember", "always", "prefer"]
                if any(kw in user_msg.lower() for kw in important_keywords):
                    importance_rating = 8

            # Formulate response showing memory usage
            ref_lines = []
            if retrieved_texts:
                ref_lines.append(f"• Retrieved episode: \"{retrieved_texts[0]}\"")
            if agent.semantic.profile:
                pref_k = list(agent.semantic.profile.keys())[0]
                pref_v = agent.semantic.profile[pref_k]
                ref_lines.append(f"• User profile lookup: {pref_k} = {pref_v}")

            if ref_lines:
                refs = "\n".join(ref_lines)
                assistant_reply = f"I retrieved the following details from my developer memory to ground this response:\n{refs}\n\nYou can adjust the retrieval weights (Recency, Importance, Relevance) in the sidebar to see how they impact context matching."
            else:
                assistant_reply = "I've registered this development detail in my episodic memory! Try telling me things like 'Our project runs on port 5000', 'We use Python with black formatting', or 'My preferred documentation style is Google style', and then click 'Consolidate (Sleep)' to build your interactive developer semantic memory graph."

    # 8. Save both turns to Short-Term Memory
    agent.short_term.add_message("user", user_msg)
    agent.short_term.add_message("assistant", assistant_reply)

    # Track assistant reply tokens
    reply_tokens = agent.short_term._estimate_tokens(assistant_reply)
    agent.total_raw_tokens += reply_tokens

    # 9. Save to Long-Term Episodic Memory
    # (Skip saving if there was an active contradiction block, to let the user resolve it first, or if we had a frustration recovery which already handled it)
    if not conflicts and not frustration_reply:
        # Embed if using Gemini
        ep_embedding = None
        if agent.gemini_api_key and HAS_GEMINI:
            try:
                import google.generativeai as genai
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=user_msg,
                    task_type="retrieval_document"
                )
                ep_embedding = result['embedding']
            except:
                pass

        # Save user memory
        agent.episodic.add_memory(
            content=user_msg,
            importance=importance_rating,
            embedding=ep_embedding,
            ymyl_category=ymyl_category,
            decay_immune=decay_immune
        )

    # Get working context token count for evaluation
    working_tokens = agent.short_term.get_total_tokens()
    compression = MemoryEvaluator.calculate_compression(agent.total_raw_tokens, working_tokens)

    retrieved_details = []
    for r in retrieved:
        retrieved_details.append({
            "id": r["memory"]["id"],
            "content": r["memory"]["content"],
            "s_recency": round(r["s_recency"], 3),
            "s_importance": round(r["s_importance"], 3),
            "s_relevance": round(r["s_relevance"], 3),
            "total_score": round(r["total_score"], 3)
        })

    return {
        "reply": assistant_reply,
        "sensory": agent.sensory.to_dict(),
        "short_term": agent.short_term.to_dict(),
        "episodic": agent.episodic.to_list(),
        "retrieved": retrieved_details,
        "semantic": agent.semantic.to_dict(),
        "compression_ratio": round(compression, 2),
        "raw_tokens": agent.total_raw_tokens,
        "working_tokens": working_tokens,
        "sanitization": sanitization_info,
        "confidence": confidence,
        "ymyl": {
            "category": ymyl_category,
            "confidence": ymyl_res.confidence,
            "decay_immune": decay_immune
        },
        "active_clarifications": active_clarifications,
        "uncertainty_guidance": uncertainty_guidance
    }

@app.post("/api/resolve_conflict")
async def resolve_conflict(payload: ConflictResolution):
    """
    Handles resolving a contradiction detected by active retrieval.
    """
    mem_id = payload.memory_id
    new_fact = payload.new_fact.strip()
    res = payload.resolution.lower().strip()

    if res == "keep_new":
        # Delete old conflicting memory
        agent.episodic.memories = [m for m in agent.episodic.memories if m["id"] != mem_id]
        
        # Save new memory
        ymyl_res = classify_ymyl_detailed(new_fact)
        ymyl_cat = ymyl_res.category
        decay_immune = ymyl_res.is_strong or (ymyl_res.is_ymyl and agent.ymyl_enabled)
        importance = 8 if ymyl_res.is_strong else 7
        
        agent.episodic.add_memory(
            content=new_fact,
            importance=importance,
            ymyl_category=ymyl_cat,
            decay_immune=decay_immune
        )
        msg = f"Resolution applied: old memory ID {mem_id} removed, and new fact stored: '{new_fact}'"
    elif res == "keep_old":
        # Keep old memory, do not save new fact
        msg = f"Resolution applied: kept existing memory ID {mem_id}, discarded new fact: '{new_fact}'"
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution action")

    # Add confirmation to short term context
    agent.short_term.add_message("system", f"[Conflict Resolved] {msg}")
    
    return {
        "status": "success",
        "message": msg,
        "episodic": agent.episodic.to_list(),
        "short_term": agent.short_term.to_dict(),
        "semantic": agent.semantic.to_dict(),
        "sensory": agent.sensory.to_dict(),
        "compression_ratio": round(MemoryEvaluator.calculate_compression(agent.total_raw_tokens, agent.short_term.get_total_tokens()), 2)
    }

@app.post("/api/config")
async def update_config(config: ConfigUpdate):
    agent.w_recency = config.w_recency
    agent.w_importance = config.w_importance
    agent.w_relevance = config.w_relevance
    
    if config.decay_function is not None:
        agent.decay_function = config.decay_function.strip()
    if config.uncertainty_mode is not None:
        agent.uncertainty_mode = config.uncertainty_mode.strip()
    if config.ymyl_enabled is not None:
        agent.ymyl_enabled = config.ymyl_enabled
    
    if config.gemini_api_key is not None:
        key = config.gemini_api_key.strip()
        if key:
            agent.gemini_api_key = key
            agent.consolidator.set_api_key(key)
            agent.active_retriever.set_api_key(key)
        else:
            agent.gemini_api_key = None
            agent.consolidator.set_api_key(None)
            agent.active_retriever.set_api_key(None)
            
    return {"status": "success", "config": {
        "w_recency": agent.w_recency,
        "w_importance": agent.w_importance,
        "w_relevance": agent.w_relevance,
        "decay_function": agent.decay_function,
        "uncertainty_mode": agent.uncertainty_mode,
        "ymyl_enabled": agent.ymyl_enabled,
        "gemini_mode_active": agent.gemini_api_key is not None
    }}

@app.post("/api/sleep")
async def sleep_consolidation():
    """
    Trigger consolidation cycle (consolidating episodic memories into semantic knowledge).
    """
    report = agent.consolidator.consolidate(agent.episodic, agent.semantic)
    return {
        "report": report,
        "semantic": agent.semantic.to_dict()
    }

@app.post("/api/clear")
async def clear_memories():
    agent.clear_all()
    return {
        "status": "cleared",
        "episodic": agent.episodic.to_list(),
        "short_term": agent.short_term.to_dict(),
        "semantic": agent.semantic.to_dict()
    }

@app.post("/api/delete_memory")
async def delete_memory(payload: DeleteMemoryRequest):
    m_type = payload.memory_type.lower()
    
    if m_type == "episodic":
        if payload.target_id is None:
            raise HTTPException(status_code=400, detail="Missing target_id for episodic deletion")
        agent.episodic.memories = [m for m in agent.episodic.memories if m["id"] != payload.target_id]
        msg = f"Episodic memory ID {payload.target_id} deleted."
        
    elif m_type == "fact":
        if not payload.target_text:
            raise HTTPException(status_code=400, detail="Missing target_text for fact deletion")
        agent.semantic.facts = [f for f in agent.semantic.facts if f != payload.target_text]
        # Also clean up semantic edges related to this fact if applicable
        msg = f"Semantic fact '{payload.target_text}' deleted."
        
    elif m_type == "profile":
        if not payload.target_key:
            raise HTTPException(status_code=400, detail="Missing target_key for profile deletion")
        if payload.target_key in agent.semantic.profile:
            del agent.semantic.profile[payload.target_key]
        msg = f"Profile key '{payload.target_key}' deleted."
        
    else:
        raise HTTPException(status_code=400, detail="Invalid memory_type")

    return {
        "status": "success",
        "message": msg,
        "episodic": agent.episodic.to_list(),
        "short_term": agent.short_term.to_dict(),
        "semantic": agent.semantic.to_dict()
    }

@app.post("/api/eval")
async def run_eval(payload: Dict[str, str] = Body(...)):
    query = payload.get("query", "profile details").strip()
    
    query_embedding = None
    if agent.gemini_api_key and HAS_GEMINI:
        try:
            import google.generativeai as genai
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            query_embedding = result['embedding']
        except:
            pass

    start_time = time.time()
    retrieved = agent.episodic.retrieve(
        query=query,
        query_embedding=query_embedding,
        w_recency=agent.w_recency,
        w_importance=agent.w_importance,
        w_relevance=agent.w_relevance,
        top_k=3,
        decay_function=agent.decay_function
    )
    latency_ms = (time.time() - start_time) * 1000

    memories = agent.episodic.to_list()
    eval_stats = MemoryEvaluator.evaluate_retrieval(retrieved, memories, query)
    compression = MemoryEvaluator.calculate_compression(agent.total_raw_tokens, agent.short_term.get_total_tokens())

    retrieved_details = []
    for r in retrieved:
        retrieved_details.append({
            "id": r["memory"]["id"],
            "content": r["memory"]["content"],
            "s_recency": round(r["s_recency"], 3),
            "s_importance": round(r["s_importance"], 3),
            "s_relevance": round(r["s_relevance"], 3),
            "total_score": round(r["total_score"], 3)
        })

    return {
        "latency_ms": round(latency_ms, 3),
        "precision": eval_stats["precision"],
        "recall": eval_stats["recall"],
        "f1_score": eval_stats["f1_score"],
        "compression_ratio": round(compression, 2),
        "retrieved": retrieved_details
    }


# ── Codebase Explorer ─────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SKIP_DIRS  = {".git", "__pycache__", ".pytest_cache", "venv", "node_modules", ".gemini"}
SKIP_FILES = {".pyc", ".pyo", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"}
MAX_FILE_BYTES = 200_000  # 200 KB cap — safety for large files

def _build_tree(root: str, rel: str = "") -> list:
    items = []
    try:
        entries = sorted(os.scandir(os.path.join(root, rel)), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return items
    for entry in entries:
        if entry.name.startswith(".") and entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            child_rel = os.path.join(rel, entry.name) if rel else entry.name
            children = _build_tree(root, child_rel)
            items.append({"name": entry.name, "path": child_rel, "type": "dir", "children": children})
        else:
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in SKIP_FILES:
                continue
            child_rel = os.path.join(rel, entry.name) if rel else entry.name
            items.append({"name": entry.name, "path": child_rel, "type": "file",
                          "size": entry.stat().st_size})
    return items

@app.get("/api/codebase")
async def get_codebase_tree():
    tree = _build_tree(PROJECT_ROOT)
    return {"root": os.path.basename(PROJECT_ROOT), "tree": tree}

@app.get("/api/file")
async def get_file_content(path: str):
    # Sanitize: resolve to absolute and ensure it's inside project root
    abs_path = os.path.normpath(os.path.join(PROJECT_ROOT, path))
    if not abs_path.startswith(PROJECT_ROOT):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found.")
    size = os.path.getsize(abs_path)
    if size > MAX_FILE_BYTES:
        return {"path": path, "content": f"[File too large to display: {size // 1024} KB]", "truncated": True}
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"path": path, "content": content, "truncated": False}

# Serve Frontend static assets

static_path = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)

app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
