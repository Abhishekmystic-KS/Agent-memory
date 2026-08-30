import time
import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional

def calculate_local_similarity(text1: str, text2: str) -> float:
    """
    Computes a bag-of-words cosine similarity between two texts.
    Used for 100% offline keyword/semantic approximation.
    """
    words1 = re.findall(r'\w+', text1.lower())
    words2 = re.findall(r'\w+', text2.lower())
    if not words1 or not words2:
        return 0.0
        
    vec1 = Counter(words1)
    vec2 = Counter(words2)
    
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    
    sum1 = sum(val**2 for val in vec1.values())
    sum2 = sum(val**2 for val in vec2.values())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    
    if not denominator:
        return 0.0
    return float(numerator) / denominator

def cosine_similarity_vectors(vec1: List[float], vec2: List[float]) -> float:
    """
    Computes the cosine similarity between two float vectors.
    """
    if len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if not norm_a or not norm_b:
        return 0.0
    return dot_product / (norm_a * norm_b)


class EpisodicMemory:
    """
    Episodic Memory represents the stream of past experiences (conversations, observations, actions).
    Each memory holds:
    - Text content
    - Creation timestamp (or simulated virtual time)
    - Importance score (1-10)
    - Optional vector embedding for semantic search
    """
    def __init__(self, decay_rate: float = 0.005):
        self.memories: List[Dict[str, Any]] = []
        self.decay_rate = decay_rate  # lambda for exponential recency decay S = exp(-lambda * delta_t)

    def add_memory(self, content: str, importance: int, embedding: Optional[List[float]] = None, timestamp: Optional[float] = None):
        """
        Record a new episodic memory.
        """
        self.memories.append({
            "id": len(self.memories) + 1,
            "content": content,
            "importance": min(max(importance, 1), 10),
            "embedding": embedding,
            "timestamp": timestamp if timestamp is not None else time.time()
        })

    def retrieve(self, query: str, query_embedding: Optional[List[float]] = None, 
                 w_recency: float = 1.0, w_importance: float = 1.0, w_relevance: float = 1.0,
                 top_k: int = 3, current_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top_k memories based on the hybrid scoring function:
        Score = w_recency * S_recency + w_importance * S_importance + w_relevance * S_relevance
        """
        if not self.memories:
            return []

        now = current_time if current_time is not None else time.time()
        scored_memories = []

        # Find min/max values to normalize scores to [0, 1] range for fair summation
        raw_recencies = []
        raw_importances = []
        raw_relevances = []

        for m in self.memories:
            # 1. Recency: exp(-lambda * delta_t_hours)
            delta_t_seconds = max(now - m["timestamp"], 0)
            delta_t_hours = delta_t_seconds / 3600.0  # Normalize time difference to hours
            s_recency = math.exp(-self.decay_rate * delta_t_hours)
            raw_recencies.append(s_recency)

            # 2. Importance
            s_importance = m["importance"] / 10.0
            raw_importances.append(s_importance)

            # 3. Relevance
            if query_embedding is not None and m["embedding"] is not None:
                s_relevance = cosine_similarity_vectors(query_embedding, m["embedding"])
            else:
                s_relevance = calculate_local_similarity(query, m["content"])
            raw_relevances.append(s_relevance)

            scored_memories.append({
                "memory": m,
                "s_recency": s_recency,
                "s_importance": s_importance,
                "s_relevance": s_relevance,
                "total_score": 0.0
            })

        # Min-max normalization helper
        def normalize(val: float, val_list: List[float]) -> float:
            min_val = min(val_list)
            max_val = max(val_list)
            if max_val - min_val == 0:
                return 1.0
            return (val - min_val) / (max_val - min_val)

        # Normalize and calculate final score
        for idx, sm in enumerate(scored_memories):
            norm_rec = normalize(sm["s_recency"], raw_recencies)
            norm_imp = normalize(sm["s_importance"], raw_importances)
            norm_rel = normalize(sm["s_relevance"], raw_relevances)

            sm["norm_recency"] = norm_rec
            sm["norm_importance"] = norm_imp
            sm["norm_relevance"] = norm_rel

            sm["total_score"] = (w_recency * norm_rec) + (w_importance * norm_imp) + (w_relevance * norm_rel)

        # Sort by total score descending
        scored_memories.sort(key=lambda x: x["total_score"], reverse=True)
        return scored_memories[:top_k]

    def clear(self):
        self.memories = []

    def to_list(self) -> List[Dict[str, Any]]:
        return self.memories
