"""Uncertainty-aware retrieval: confidence assessment, frustration detection, and response guidance.
"""

import re
from typing import List, Dict, Any, Optional

_DEFAULT_THRESHOLDS = {
    "high": 0.45,
    "moderate": 0.25,
    "low": 0.12,
}

FRUSTRATION_SIGNALS = (
    "i told you", "i already said", "remember when i", "i mentioned",
    "you forgot", "you should know", "we talked about", "i said before",
    "don't you remember", "how could you forget", "i literally told",
    "we discussed", "you should remember", "i specifically said",
)

def assess_confidence(results: List[Dict[str, Any]], similarity_key: str = "s_relevance") -> str:
    """Assess retrieval confidence based on top similarity score in results."""
    if not results:
        return "none"

    # Get similarity score of top retrieval match
    top_result = results[0]
    top_sim = top_result.get(similarity_key, 0.0)

    if top_sim >= _DEFAULT_THRESHOLDS["high"]:
        return "high"
    if top_sim >= _DEFAULT_THRESHOLDS["moderate"]:
        return "moderate"
    if top_sim >= _DEFAULT_THRESHOLDS["low"]:
        return "low"
    return "none"

def detect_frustration(query: str) -> bool:
    """Detect if the user is frustrated about a forgotten memory."""
    q = query.lower()
    return any(signal in q for signal in FRUSTRATION_SIGNALS)

def extract_forgotten_fact(query: str) -> Optional[str]:
    """Extracts the fact a user is reminding the agent about."""
    q = query.strip()
    patterns = [
        r"(?:i\s+told\s+you|i\s+already\s+said|i\s+mentioned)\s+(?:that\s+)?(.+?)[\.\!\?]?$",
        r"(?:remember\s+(?:that\s+)?(?:i\s+)?(?:said\s+)?(?:that\s+)?)(.+?)[\.\!\?]?$",
        r"(?:you\s+forgot|don'?t\s+you\s+remember)\s+(?:that\s+)?(?:i\s+)?(.+?)[\.\!\?]?$",
        r"(?:i\s+specifically\s+said|i\s+literally\s+told\s+you)\s+(?:that\s+)?(.+?)[\.\!\?]?$",
    ]
    vague_phrases = {"something", "something important", "that", "this", "it",
                     "stuff", "things", "that thing", "about that", "about it",
                     "this already", "that already", "this before", "that before"}
    for pattern in patterns:
        match = re.search(pattern, q, re.IGNORECASE)
        if match:
            fact = match.group(1).strip().rstrip("!.?")
            if len(fact) > 8 and fact.lower() not in vague_phrases:
                return fact
    return None

def build_uncertainty_guidance(
    confidence: str,
    mode: str,
    results: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Build guidance about how to handle uncertain memory retrieval.

    Returns None if confidence is high.
    """
    confidence = confidence.lower().strip()
    mode = mode.lower().strip()

    if confidence == "high":
        return None

    if confidence == "none":
        if mode == "strict":
            return {"action": "refuse", "message": "I don't have any memories about this."}
        if mode == "helpful":
            return {"action": "refuse", "message": "I don't have specific information about this stored."}
        # creative
        return {
            "action": "offer_guess",
            "message": "I don't have this in my memory — I can take a guess based on what I do know, if you'd like.",
        }

    related = [r["memory"]["content"][:80] for r in results[:3]] if results else []

    if confidence == "low":
        if mode == "strict":
            return {"action": "refuse", "message": "I'm not confident I have relevant information about this."}
        if mode == "helpful":
            return {
                "action": "hedge",
                "message": "I don't have a direct answer, but I know some related things.",
                "related": related,
            }
        # creative
        return {
            "action": "offer_guess",
            "message": "I'm not sure about this, but I have some related memories — want me to guess?",
            "related": related,
        }

    # moderate confidence
    if mode == "strict":
        return {"action": "hedge", "message": "I have some information but I'm not fully certain."}
    return {
        "action": "answer",
        "message": "Based on what I remember (though I'm not 100% certain):",
    }

def build_frustration_response(
    query: str,
    confidence: str,
    mode: str
) -> Optional[Dict[str, Any]]:
    """Generates guidance when a frustrated user is reminding the agent."""
    if not detect_frustration(query):
        return None

    fact = extract_forgotten_fact(query)

    if confidence in ("high", "moderate"):
        return {
            "action": "reassure",
            "message": "I do have some information about this — let me check.",
            "pin_fact": None,
        }

    if fact:
        return {
            "action": "recover_and_pin",
            "message": "Sorry about that. I'm saving this now with high importance so I won't forget again.",
            "pin_fact": fact,
            "pin_importance": 9.0,
        }

    return {
        "action": "apologize_and_ask",
        "message": "I'm sorry, I don't seem to have that stored. Could you tell me again? I'll make sure it sticks this time.",
        "pin_fact": None,
    }
