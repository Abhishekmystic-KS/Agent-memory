import re
import json
import logging
from typing import List, Dict, Any, Optional
from bottleneck.episodic import EpisodicMemory
from bottleneck.semantic import SemanticMemory

logger = logging.getLogger(__name__)

# Try to import Google GenAI library. If not installed, we fallback gracefully.
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

class MemoryConsolidator:
    """
    MemoryConsolidator manages the Sleep/Reflect cycle of the agent.
    It reads recent experiences from EpisodicMemory and consolidates them into SemanticMemory,
    updating the User Profile, extracting general facts, and building the entity-relationship graph.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if api_key and HAS_GEMINI:
            genai.configure(api_key=api_key)

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        if HAS_GEMINI:
            genai.configure(api_key=api_key)

    def consolidate(self, episodic_mem: EpisodicMemory, semantic_mem: SemanticMemory) -> Dict[str, Any]:
        """
        Executes the consolidation cycle.
        Returns a summary report of changes made (new facts, updated profile, new edges).
        """
        memories = episodic_mem.to_list()
        if not memories:
            return {"status": "ignored", "reason": "No episodic memories to consolidate."}

        # Check if we should use Gemini or Heuristics
        if self.api_key and HAS_GEMINI:
            try:
                return self._consolidate_with_gemini(memories, semantic_mem)
            except Exception as e:
                logger.error(f"Gemini consolidation failed, falling back to heuristics: {e}")
                return self._consolidate_with_heuristics(memories, semantic_mem)
        else:
            return self._consolidate_with_heuristics(memories, semantic_mem)

    def _consolidate_with_heuristics(self, memories: List[Dict[str, Any]], semantic_mem: SemanticMemory) -> Dict[str, Any]:
        """
        Consolidation fallback using pattern matching / regex.
        Extracts key-value pairs and entity relations from dialogue text.
        """
        report = {
            "mode": "heuristic",
            "profile_updates": {},
            "new_facts": [],
            "new_relations": []
        }

        # Profile pattern rules: (pattern, profile_key)
        profile_rules = [
            (r"(?:my name is|i am|i'm)\s+([a-zA-Z]+)", "name"),
            (r"(?:i live in|i'm from|i reside in)\s+([a-zA-Z\s,]+)", "location"),
            (r"(?:i work as a|i work as an|i am a|i'm a|i'm an)\s+([a-zA-Z\s]+)", "occupation"),
            (r"(?:my favorite color is|i love the color|i like the color)\s+([a-zA-Z\s]+)", "favorite_color"),
            (r"(?:i code in|my favorite programming language is|i use)\s+(python|javascript|typescript|c\+\+|rust|golang|java|ruby)", "coding_language"),
        ]

        # Relationship rules: (pattern, relation, source, target index)
        # e.g., "I love green tea" -> User -> likes -> green tea
        relation_rules = [
            (r"(?:i like|i love|i enjoy)\s+([a-zA-Z\s]+)", "likes", "User", 0),
            (r"(?:i hate|i dislike|i don't like)\s+([a-zA-Z\s]+)", "dislikes", "User", 0),
            (r"([a-zA-Z\s]+)\s+(?:is written in|runs on)\s+([a-zA-Z\s]+)", "technology_stack", 0, 1),
            (r"([a-zA-Z\s]+)\s+(?:works at|is employed by)\s+([a-zA-Z\s]+)", "works_at", 0, 1)
        ]

        for m in memories:
            content = m["content"]
            
            # 1. Profile Extraction
            for pattern, key in profile_rules:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    val = match.group(1).strip()
                    # Strip trailing periods/whitespace
                    val = re.sub(r'[.\s]+$', '', val)
                    if len(val) < 40:  # Ignore overly long sentences
                        semantic_mem.update_profile(key, val)
                        report["profile_updates"][key] = val

            # 2. Relation Extraction
            for pattern, relation, src_val, tgt_idx in relation_rules:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if src_val == "User":
                        target = groups[0].strip()
                        target = re.sub(r'[.\s]+$', '', target)
                        if len(target) < 30:
                            semantic_mem.add_relation("User", relation, target)
                            report["new_relations"].append(f"User -({relation})-> {target}")
                    else:
                        source = groups[0].strip()
                        target = groups[1].strip()
                        source = re.sub(r'[.\s]+$', '', source)
                        target = re.sub(r'[.\s]+$', '', target)
                        if len(source) < 30 and len(target) < 30:
                            semantic_mem.add_relation(source, relation, target)
                            report["new_relations"].append(f"{source} -({relation})-> {target}")

            # 3. Fact Generalization
            # If the entry contains structured facts, add them directly
            if len(content.split()) < 15 and ("like" in content.lower() or "is" in content.lower() or "study" in content.lower()):
                cleaned_fact = re.sub(r'[.\s]+$', '', content)
                semantic_mem.add_fact(cleaned_fact)
                report["new_facts"].append(cleaned_fact)

        return report

    def _consolidate_with_gemini(self, memories: List[Dict[str, Any]], semantic_mem: SemanticMemory) -> Dict[str, Any]:
        """
        Consolidation utilizing Google Gemini.
        Extracts structured facts, updates profiles, and builds entity relationships.
        """
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Formulate memory log
        memory_log = "\n".join([f"- [{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamp']))}] {m['content']}" for m in memories])

        prompt = f"""
You are the memory consolidation controller of an AI agent. 
Analyze the following episodic memory stream log of recent interactions.
Your task is to extract:
1. User Profile: Key-value updates to the user profile (e.g., name, location, likes, job, preferences).
2. Entity Relationships: Triples of (source, relation, target) showing conceptual relationships (e.g. ("User", "studies", "Agent Memory"), ("Python", "uses", "Pip")).
3. General Facts: Important general facts about the world, user, or projects.

Resolve contradictions: if newer memories conflict with older ones, choose the newer details.

Current User Profile:
{json.dumps(semantic_mem.profile, indent=2)}

Recent Episodic Memories:
{memory_log}

Return the output strictly in the following JSON format:
{{
  "profile_updates": {{
     "key": "value"
  }},
  "new_relations": [
     {{"source": "entity1", "relation": "relationship", "target": "entity2"}}
  ],
  "new_facts": [
     "fact string"
  ]
}}
Do not include any Markdown wrapping like ```json or additional notes. Just the raw JSON object.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Strip markdown markers if present
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        data = json.loads(text)

        # Apply to semantic store
        for k, v in data.get("profile_updates", {}).items():
            semantic_mem.update_profile(k, v)

        for rel in data.get("new_relations", []):
            semantic_mem.add_relation(rel["source"], rel["relation"], rel["target"])

        for fact in data.get("new_facts", []):
            semantic_mem.add_fact(fact)

        return {
            "mode": "gemini",
            "profile_updates": data.get("profile_updates", {}),
            "new_facts": data.get("new_facts", []),
            "new_relations": [f"{r['source']} -({r['relation']})-> {r['target']}" for r in data.get("new_relations", [])]
        }
