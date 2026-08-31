from typing import List, Dict, Any, Optional, Set

class SemanticMemory:
    """
    Semantic Memory stores structured facts, user preferences, and relations.
    Unlike Episodic Memory which is time-bound and experiential, Semantic Memory
    represents consolidated, generalized knowledge about the world, entities, and the user.
    """
    def __init__(self):
        # User details profile (key-value)
        self.profile: Dict[str, str] = {}
        # List of general facts
        self.facts: List[str] = []
        # Entity-Relationship Graph
        self.entities: Set[str] = set()
        self.edges: List[Dict[str, str]] = []  # List of {"source": str, "target": str, "relation": str}

    def update_profile(self, key: str, value: str):
        """
        Add or update a key-value pair in the user profile.
        """
        self.profile[key.lower().strip()] = value.strip()

    def add_fact(self, fact: str):
        """
        Add a generalized fact. Avoid duplicates.
        """
        cleaned = fact.strip()
        if cleaned and cleaned not in self.facts:
            self.facts.append(cleaned)

    def add_relation(self, source: str, relation: str, target: str):
        """
        Add an entity relationship: source -> relation -> target.
        Updates entity list automatically.
        """
        src = source.strip()
        rel = relation.strip().lower()
        tgt = target.strip()
        
        self.entities.add(src)
        self.entities.add(tgt)
        
        # Check if relationship already exists
        exists = any(
            e["source"] == src and e["relation"] == rel and e["target"] == tgt
            for e in self.edges
        )
        if not exists:
            self.edges.append({
                "source": src,
                "relation": rel,
                "target": tgt
            })

    def get_related_entities(self, entity: str) -> List[Dict[str, str]]:
        """
        Get all edges connected to/from a given entity.
        """
        ent_lower = entity.lower().strip()
        results = []
        for edge in self.edges:
            if edge["source"].lower() == ent_lower or edge["target"].lower() == ent_lower:
                results.append(edge)
        return results

    def clear(self):
        self.profile = {}
        self.facts = []
        self.entities = set()
        self.edges = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "facts": self.facts,
            "entities": list(self.entities),
            "edges": self.edges
        }
