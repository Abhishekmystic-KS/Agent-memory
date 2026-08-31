"""Active retrieval: detects conflicts, contradictions, and ambiguities between new and existing facts.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import Google GenAI
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

class Clarification:
    def __init__(self, new_fact: str, existing_content: str, existing_memory_id: int, conflict_type: str, question: str):
        self.new_fact = new_fact
        self.existing_content = existing_content
        self.existing_memory_id = existing_memory_id
        self.conflict_type = conflict_type  # "contradiction" or "ambiguity"
        self.question = question

    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_fact": self.new_fact,
            "existing_content": self.existing_content,
            "existing_memory_id": self.existing_memory_id,
            "conflict_type": self.conflict_type,
            "question": self.question
        }

class ActiveRetrieval:
    def __init__(self, similarity_threshold: float = 0.45, api_key: Optional[str] = None):
        self.similarity_threshold = similarity_threshold
        self.api_key = api_key
        if api_key and HAS_GEMINI:
            genai.configure(api_key=api_key)

    def set_api_key(self, api_key: Optional[str]):
        self.api_key = api_key
        if api_key and HAS_GEMINI:
            genai.configure(api_key=api_key)

    def detect_conflicts(
        self,
        new_fact: str,
        existing_memories: List[Dict[str, Any]]
    ) -> List[Clarification]:
        """Detects contradictions or ambiguities between the new fact and existing memories."""
        if not new_fact or not existing_memories:
            return []

        # Filter memories that meet the similarity/relevance threshold
        relevant_memories = [
            m for m in existing_memories
            if m.get("s_relevance", 0.0) >= self.similarity_threshold or m.get("total_score", 0.0) >= self.similarity_threshold
        ]

        if not relevant_memories:
            return []

        if self.api_key and HAS_GEMINI:
            try:
                return self._detect_with_gemini(new_fact, relevant_memories)
            except Exception as e:
                logger.error(f"Gemini conflict detection failed, falling back to heuristics: {e}")
                return self._detect_with_heuristics(new_fact, relevant_memories)
        else:
            return self._detect_with_heuristics(new_fact, relevant_memories)

    def _detect_with_heuristics(
        self,
        new_fact: str,
        relevant_memories: List[Dict[str, Any]]
    ) -> List[Clarification]:
        """Heuristic conflict detection based on phrase mapping rules."""
        conflicts: List[Clarification] = []
        new_fact_lower = new_fact.lower()

        # Define rule patterns and their extraction regexes
        rules = [
            # Name rule
            {
                "patterns": [r"(?:my name is|i am|i'm)\s+([a-zA-Z\s]+)"],
                "subject": "name",
                "question": "You previously mentioned your name was '{old}', but now you say it is '{new}'. Has your name changed?"
            },
            # Location rule
            {
                "patterns": [r"(?:i live in|i'm in|i moved to|i'm from)\s+([a-zA-Z\s]+)"],
                "subject": "location",
                "question": "I remember you living in '{old}', but now you say you are in '{new}'. Did you move?"
            },
            # Occupation rule
            {
                "patterns": [r"(?:i work as a|i work as an|i am a|i'm a|i'm an|my job is)\s+([a-zA-Z\s]+)"],
                "subject": "occupation",
                "question": "You previously said you work as a '{old}', but now you say '{new}'. Did you change careers?"
            },
            # Favorite color rule
            {
                "patterns": [r"(?:my favorite color is|i love the color|i like the color)\s+([a-zA-Z\s]+)"],
                "subject": "favorite color",
                "question": "You mentioned your favorite color was '{old}', but now you like '{new}'. Did your preference change?"
            },
        ]

        for rule in rules:
            new_val = None
            for p in rule["patterns"]:
                m = re.search(p, new_fact_lower, re.IGNORECASE)
                if m:
                    new_val = m.group(1).strip().rstrip("?.!")
                    break

            if not new_val:
                continue

            # Compare against relevant existing memories
            for existing in relevant_memories:
                content = existing["memory"]["content"]
                content_lower = content.lower()
                old_val = None
                for p in rule["patterns"]:
                    m = re.search(p, content_lower, re.IGNORECASE)
                    if m:
                        old_val = m.group(1).strip().rstrip("?.!")
                        break

                if old_val and old_val != new_val:
                    # Found a mismatch/contradiction!
                    question = rule["question"].format(old=old_val.capitalize(), new=new_val.capitalize())
                    conflicts.append(Clarification(
                        new_fact=new_fact,
                        existing_content=content,
                        existing_memory_id=existing["memory"]["id"],
                        conflict_type="contradiction",
                        question=question
                    ))
                    break  # Keep to one conflict per type for simplicity

        # Fallback: simple negation detector
        if not conflicts:
            for existing in relevant_memories:
                content = existing["memory"]["content"]
                # Check for direct contradictions like "I like cats" vs "I don't like cats"
                if self._is_negated_pair(new_fact_lower, content.lower()):
                    conflicts.append(Clarification(
                        new_fact=new_fact,
                        existing_content=content,
                        existing_memory_id=existing["memory"]["id"],
                        conflict_type="contradiction",
                        question=f"I have recorded: '{content}'. But you just said: '{new_fact}'. Which is correct?"
                    ))
                    break

        return conflicts

    def _is_negated_pair(self, s1: str, s2: str) -> bool:
        """Determines if s1 and s2 are opposites (e.g. 'i like python' vs 'i don't like python')."""
        def clean_negatives(s: str) -> str:
            s = re.sub(r"\b(don't|do not|dislike|hate|never|no longer)\b", "[NEG]", s)
            s = re.sub(r"[^\w\s\[\]]", "", s)
            return s

        c1 = clean_negatives(s1)
        c2 = clean_negatives(s2)

        # If one is negated and the other isn't, and they match otherwise:
        if ("[NEG]" in c1 and "[NEG]" not in c2) or ("[NEG]" in c2 and "[NEG]" not in c1):
            w1 = set(c1.replace("[NEG]", "").split())
            w2 = set(c2.replace("[NEG]", "").split())
            intersection = w1 & w2
            union = w1 | w2
            if union and len(intersection) / len(union) > 0.7:
                return True
        return False

    def _detect_with_gemini(
        self,
        new_fact: str,
        relevant_memories: List[Dict[str, Any]]
    ) -> List[Clarification]:
        """Detect conflicts using Google Gemini."""
        model = genai.GenerativeModel('gemini-1.5-flash')

        existing_str = "\n".join(
            f"[{m['memory']['id']}] {m['memory']['content']}"
            for m in relevant_memories
        )

        prompt = f"""
You are the conflict detection engine of an AI agent's memory system.
Analyze the following new fact and compare it against the user's existing memories to identify contradictions or ambiguities.

New Fact:
"{new_fact}"

Existing Similar Memories:
{existing_str}

Check if there are direct contradictions (e.g. living in a different place, changing name, opposing preference) or ambiguities.
If there is a conflict, formulate a helpful clarifying question to ask the user.

Return the output strictly in the following JSON format:
{{
  "has_conflict": true/false,
  "conflicts": [
     {{
       "existing_memory_id": 123,
       "existing_content": "original memory content",
       "type": "contradiction" or "ambiguity",
       "question": "clarifying question to user"
     }}
  ]
}}
Do not include any Markdown wrapping like ```json or additional notes. Just the raw JSON.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        data = json.loads(text)
        conflicts = []

        if data.get("has_conflict", False):
            for conflict in data.get("conflicts", []):
                mem_id = int(conflict["existing_memory_id"])
                conflicts.append(Clarification(
                    new_fact=new_fact,
                    existing_content=conflict["existing_content"],
                    existing_memory_id=mem_id,
                    conflict_type=conflict.get("type", "contradiction"),
                    question=conflict["question"]
                ))
        return conflicts
