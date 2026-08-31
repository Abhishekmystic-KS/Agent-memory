import time
from typing import List, Dict, Any

class MemoryEvaluator:
    """
    MemoryEvaluator tracks and calculates key metrics for assessing the efficiency and quality
    of an agent's memory architecture.
    """
    
    @staticmethod
    def calculate_compression(raw_tokens: int, working_tokens: int) -> float:
        """
        Calculates context compression ratio.
        Higher means more token savings for the LLM context window.
        """
        if raw_tokens == 0:
            return 0.0
        return max(0.0, 1.0 - (working_tokens / raw_tokens))

    @staticmethod
    def evaluate_retrieval(retrieved: List[Dict[str, Any]], all_memories: List[Dict[str, Any]], 
                           query: str, similarity_threshold: float = 0.15) -> Dict[str, Any]:
        """
        Evaluates retrieval quality (Precision and Recall) using keyword/similarity heuristics.
        - Ground truth: memories in the database that match keywords or have a similarity above threshold.
        """
        # Determine "ground truth" relevant memories based on similarity threshold
        # In a real environment, we'd use human labels or a strong LLM judge.
        from bottleneck.episodic import calculate_local_similarity
        
        ground_truth_indices = []
        for idx, m in enumerate(all_memories):
            sim = calculate_local_similarity(query, m["content"])
            if sim >= similarity_threshold:
                ground_truth_indices.append(m["id"])

        if not ground_truth_indices:
            # If no memories are actually relevant, precision/recall are tricky.
            # We return empty stats
            return {
                "precision": 1.0 if not retrieved else 0.0,
                "recall": 1.0,
                "f1_score": 1.0 if not retrieved else 0.0,
                "retrieved_count": len(retrieved),
                "ground_truth_count": 0
            }

        retrieved_ids = [r["memory"]["id"] for r in retrieved]
        relevant_retrieved = [rid for rid in retrieved_ids if rid in ground_truth_indices]

        precision = len(relevant_retrieved) / len(retrieved_ids) if retrieved_ids else 0.0
        recall = len(relevant_retrieved) / len(ground_truth_indices)

        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "f1_score": round(f1, 2),
            "retrieved_count": len(retrieved_ids),
            "ground_truth_count": len(ground_truth_indices)
        }

    @classmethod
    def run_benchmark(cls, episodic_store) -> Dict[str, Any]:
        """
        Runs a standard memory retrieval benchmark and reports stats.
        """
        memories = episodic_store.to_list()
        if len(memories) == 0:
            return {"status": "error", "message": "No memories stored. Add memories first."}

        # Run benchmark on a general query
        start_time = time.time()
        # Retrieve memories matching a general concept
        retrieved = episodic_store.retrieve(
            query="preferences interests likes", 
            w_recency=0.5, w_importance=0.5, w_relevance=1.0, 
            top_k=3
        )
        latency_ms = (time.time() - start_time) * 1000

        retrieval_stats = cls.evaluate_retrieval(retrieved, memories, "preferences interests likes")

        return {
            "latency_ms": round(latency_ms, 3),
            "retrieved_ids": [r["memory"]["id"] for r in retrieved],
            **retrieval_stats
        }
