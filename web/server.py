import os
import time
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from aether_memory.sensory import SensoryMemory
from aether_memory.short_term import ShortTermMemory
from aether_memory.episodic import EpisodicMemory
from aether_memory.semantic import SemanticMemory
from aether_memory.consolidation import MemoryConsolidator, HAS_GEMINI
from aether_memory.evaluator import MemoryEvaluator

app = FastAPI(title="AetherMemory Playground Backend")

# In-memory agent state
class AgentHarness:
    def __init__(self):
        self.sensory = SensoryMemory()
        self.short_term = ShortTermMemory(max_tokens=1500, max_turns=6)
        self.episodic = EpisodicMemory(decay_rate=0.005)
        self.semantic = SemanticMemory()
        self.consolidator = MemoryConsolidator()
        
        # Configuration
        self.w_recency = 1.0
        self.w_importance = 1.0
        self.w_relevance = 1.0
        self.gemini_api_key: Optional[str] = None
        self.total_raw_tokens = 0  # To measure compression
        
    def clear_all(self):
        self.sensory.clear()
        self.short_term.clear()
        self.episodic.clear()
        self.semantic.clear()
        self.total_raw_tokens = 0

agent = AgentHarness()

# Pydantic models for API
class ChatMessage(BaseModel):
    message: str

class ConfigUpdate(BaseModel):
    w_recency: float
    w_importance: float
    w_relevance: float
    gemini_api_key: Optional[str] = None

# API Endpoints
@app.post("/api/chat")
async def chat_endpoint(payload: ChatMessage):
    user_msg = payload.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Empty message")

    # 1. Update Sensory memory
    agent.sensory.update(raw_input=user_msg, active_goal="Respond to user message")

    # Track raw input tokens
    msg_tokens = agent.short_term._estimate_tokens(user_msg)
    agent.total_raw_tokens += msg_tokens

    # 2. Retrieve relevant episodes from Long-Term Episodic Memory
    # Fetch embedding if in Gemini mode (for now we let retrieve use its fallback or Gemini if configured)
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
        top_k=3
    )

    # Extract clean text from retrieved memories
    retrieved_texts = [r["memory"]["content"] for r in retrieved]

    # 3. Formulate the response
    assistant_reply = ""
    importance_rating = 5  # Default importance

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
            # Format input for gemini model (translate system prompts/contents to Gemini style)
            combined_prompt = ""
            for msg in prompt_messages:
                combined_prompt += f"{msg['role'].upper()}: {msg['content']}\n\n"
            combined_prompt += "ASSISTANT:"

            response = model.generate_content(combined_prompt)
            assistant_reply = response.text.strip()

            # Estimate importance rating using Gemini
            imp_prompt = f"Rate the personal or informational importance of this user message from 1 to 10 (where 10 is crucial personal facts or permanent preferences, 1 is small talk/greetings). Return ONLY a single integer digit:\nUser: {user_msg}"
            imp_res = model.generate_content(imp_prompt).text.strip()
            try:
                importance_rating = int(re.search(r'\d+', imp_res).group())
            except:
                importance_rating = 5
        except Exception as e:
            print(f"Gemini response generation failed: {e}")
            assistant_reply = f"Error in Gemini Mode: {e}. Falling back to Mock responses."
            agent.gemini_api_key = None  # Reset key or fallback

    # Heuristic/Mock response generation if not using Gemini
    if not assistant_reply:
        # Rate importance heuristically
        importance_rating = 2
        important_keywords = ["name", "live", "work", "job", "study", "code", "favorite", "like", "dislike", "hate", "remember", "always", "prefer"]
        if any(kw in user_msg.lower() for kw in important_keywords):
            importance_rating = 8
            
        # Formulate educational response showing memory usage
        ref_lines = []
        if retrieved_texts:
            ref_lines.append(f"• Retrieved episode: \"{retrieved_texts[0]}\"")
        if agent.semantic.profile:
            pref_k = list(agent.semantic.profile.keys())[0]
            pref_v = agent.semantic.profile[pref_k]
            ref_lines.append(f"• User profile lookup: {pref_k} = {pref_v}")

        if ref_lines:
            refs = "\n".join(ref_lines)
            assistant_reply = f"I retrieved the following details from my long-term memory to help answer your query:\n{refs}\n\nHow does this memory rank? You can adjust the retrieval sliders (Recency, Importance, Relevance) in the dashboard to see how different memories rank in real-time."
        else:
            assistant_reply = "I've saved this message in my episodic memory! Try telling me things like 'My name is Kali', 'I live in India', or 'I like Rust programming', and then click the 'Sleep & Consolidate' button to transfer these into my structured long-term semantic memory."

    # 4. Save both turns to Short-Term Memory
    agent.short_term.add_message("user", user_msg)
    agent.short_term.add_message("assistant", assistant_reply)

    # Track assistant reply tokens
    reply_tokens = agent.short_term._estimate_tokens(assistant_reply)
    agent.total_raw_tokens += reply_tokens

    # 5. Save to Long-Term Episodic Memory
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
    agent.episodic.add_memory(content=user_msg, importance=importance_rating, embedding=ep_embedding)

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
        "working_tokens": working_tokens
    }

@app.post("/api/config")
async def update_config(config: ConfigUpdate):
    agent.w_recency = config.w_recency
    agent.w_importance = config.w_importance
    agent.w_relevance = config.w_relevance
    
    if config.gemini_api_key is not None:
        key = config.gemini_api_key.strip()
        if key:
            agent.gemini_api_key = key
            agent.consolidator.set_api_key(key)
        else:
            agent.gemini_api_key = None
            agent.consolidator.set_api_key(None)
            
    return {"status": "success", "config": {
        "w_recency": agent.w_recency,
        "w_importance": agent.w_importance,
        "w_relevance": agent.w_relevance,
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
    return {"status": "cleared"}

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
        top_k=3
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

# Serve Frontend static assets
static_path = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)

app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
