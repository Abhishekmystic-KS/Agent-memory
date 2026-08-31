import time
import pytest
from bottleneck.sensory import SensoryMemory
from bottleneck.short_term import ShortTermMemory
from bottleneck.episodic import EpisodicMemory, calculate_local_similarity
from bottleneck.semantic import SemanticMemory
from bottleneck.consolidation import MemoryConsolidator
from bottleneck.evaluator import MemoryEvaluator

def test_sensory_memory():
    sm = SensoryMemory()
    assert sm.raw_observation is None
    
    sm.update("Hello Agent", active_goal="test")
    assert sm.raw_observation == "Hello Agent"
    assert sm.active_goal == "test"
    assert sm.timestamp > 0
    
    sm.clear()
    assert sm.raw_observation is None

def test_short_term_memory():
    # Set low limits to trigger summarization quickly
    stm = ShortTermMemory(max_tokens=300, max_turns=3)
    
    stm.add_message("user", "Hello assistant, remember my favorite language is Python.")
    stm.add_message("assistant", "I will remember that you code in Python.")
    
    assert len(stm.messages) == 2
    assert "Python" in stm.messages[0]["content"]
    
    # Adding a 4th message should trigger rolling summarization of the oldest turns (0 and 1)
    stm.add_message("user", "What is my name?")
    stm.add_message("assistant", "You haven't told me your name yet.")
    
    # Check that older turns got consolidated into rolling summary and removed from active buffer
    assert len(stm.messages) <= 3
    assert stm.rolling_summary != ""
    assert "user: hello assistant" in stm.rolling_summary.lower()

def test_episodic_memory_retrieval():
    em = EpisodicMemory(decay_rate=0.1)
    
    t_now = time.time()
    # Add memories at different times and with different importance
    # Memory 1: Old but high importance, matches "python" query
    em.add_memory("I love coding in python", importance=9, timestamp=t_now - 7200) # 2 hours ago
    # Memory 2: New, low importance, matches "python" query
    em.add_memory("Python is simple to write", importance=2, timestamp=t_now) # Just now
    # Memory 3: New, medium importance, completely different topic
    em.add_memory("The weather is nice today", importance=5, timestamp=t_now - 10)
    
    # Retrieve with relevance-only
    retrieved = em.retrieve("python language", w_recency=0.0, w_importance=0.0, w_relevance=1.0, top_k=2, current_time=t_now)
    assert len(retrieved) == 2
    # Both matches should be python related
    assert "python" in retrieved[0]["memory"]["content"].lower()
    assert "python" in retrieved[1]["memory"]["content"].lower()
    
    # Retrieve with high recency weight - "Python is simple to write" should score higher than the 2-hour-old one
    retrieved_recency = em.retrieve("python", w_recency=2.0, w_importance=0.0, w_relevance=1.0, top_k=1, current_time=t_now)
    assert retrieved_recency[0]["memory"]["content"] == "Python is simple to write"

def test_semantic_memory():
    sem = SemanticMemory()
    
    sem.update_profile("name", "Kali")
    assert sem.profile["name"] == "Kali"
    
    sem.add_fact("Kali studies AI agent memory.")
    assert "Kali studies AI agent memory." in sem.facts
    
    sem.add_relation("User", "likes", "FastAPI")
    assert len(sem.edges) == 1
    assert sem.edges[0]["source"] == "User"
    assert sem.edges[0]["relation"] == "likes"
    assert sem.edges[0]["target"] == "FastAPI"
    
    related = sem.get_related_entities("User")
    assert len(related) == 1

def test_memory_consolidation_heuristic():
    em = EpisodicMemory()
    sem = SemanticMemory()
    consolidator = MemoryConsolidator()
    
    # Add episodic interactions containing profile details
    em.add_memory("My name is Kali and I live in India", importance=8)
    em.add_memory("I work as a researcher", importance=8)
    em.add_memory("FastAPI is written in Python", importance=5)
    
    report = consolidator.consolidate(em, sem)
    
    assert report["mode"] == "heuristic"
    assert sem.profile["name"] == "Kali"
    assert sem.profile["location"] == "India"
    assert sem.profile["occupation"] == "researcher"
    
    # Check relationship graph extraction
    edges = sem.edges
    assert any(e["source"] == "FastAPI" and e["relation"] == "technology_stack" and e["target"] == "Python" for e in edges)

def test_evaluator():
    raw_tokens = 1000
    working_tokens = 200
    comp = MemoryEvaluator.calculate_compression(raw_tokens, working_tokens)
    assert comp == 0.8
    
    # Precision/recall evaluation
    all_m = [
        {"id": 1, "content": "I like python"},
        {"id": 2, "content": "I enjoy java"},
        {"id": 3, "content": "I love green tea"}
    ]
    
    retrieved = [
        {"memory": {"id": 1, "content": "I like python"}},
        {"memory": {"id": 2, "content": "I enjoy java"}}
    ]
    
    stats = MemoryEvaluator.evaluate_retrieval(retrieved, all_m, "programming languages python java", similarity_threshold=0.1)
    # Both retrieved items match the programming theme keywords, so precision and recall should be high.
    assert stats["precision"] > 0.0
    assert stats["recall"] > 0.0
