import time
from typing import List, Dict, Any, Optional

class ShortTermMemory:
    """
    Short-Term Memory (Working Memory) manages the immediate dialogue session context.
    It tracks the conversational message stream, estimates token consumption,
    and automatically triggers a rolling summary when the context limits are exceeded.
    """
    def __init__(self, max_tokens: int = 1500, max_turns: int = 6):
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []  # List of {"role": str, "content": str, "timestamp": float}
        self.rolling_summary: str = ""
        self.system_instruction: str = "You are Bottleneck, a premium developer memory companion. You help Claude Codex and the developer keep track of programming languages, style guidelines, project architecture, codebase paths, configurations, and session goals."

    def add_message(self, role: str, content: str):
        """
        Add a message to the working memory.
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self._check_and_summarize()

    def _estimate_tokens(self, text: str) -> int:
        # Simple heuristic: 1 word ≈ 1.3 tokens
        return int(len(text.split()) * 1.3) + 4

    def get_total_tokens(self) -> int:
        summary_tokens = self._estimate_tokens(self.rolling_summary) if self.rolling_summary else 0
        system_tokens = self._estimate_tokens(self.system_instruction)
        messages_tokens = sum(self._estimate_tokens(m["content"]) for m in self.messages)
        return summary_tokens + system_tokens + messages_tokens

    def _check_and_summarize(self):
        """
        If the conversation buffer exceeds the max token limit or turn limit,
        compress the oldest messages into the rolling summary.
        """
        while len(self.messages) > self.max_turns or self.get_total_tokens() > self.max_tokens:
            if len(self.messages) <= 2:
                # Keep at least the latest user and assistant turn if possible
                break
                
            # Take the oldest pair (User + Assistant response) to summarize
            turns_to_summarize = []
            if len(self.messages) >= 2:
                turns_to_summarize = [self.messages.pop(0), self.messages.pop(0)]
            else:
                turns_to_summarize = [self.messages.pop(0)]
                
            self._update_summary(turns_to_summarize)

    def _update_summary(self, turns: List[Dict[str, Any]]):
        """
        Appends the given turns to the rolling summary.
        In a production agent, this would be an LLM call.
        In our simulator, we will use a high-quality heuristic summary generator,
        or let the main orchestrator trigger a real LLM-based summary if in Gemini Mode.
        """
        formatted_turns = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in turns])
        
        # Simple local text summarization heuristic for offline/mock mode:
        # Extract main topics and concatenate them
        if not self.rolling_summary:
            self.rolling_summary = "Summary of earlier conversation: "
            
        topics = []
        for t in turns:
            content = t['content']
            # Heuristic: Find words starting with capital letters, or sentences.
            # Just extract a brief clip
            words = content.split()
            if len(words) > 8:
                summary_snippet = " ".join(words[:8]) + "..."
            else:
                summary_snippet = content
            topics.append(f"{t['role']}: {summary_snippet}")
            
        self.rolling_summary += "; " + ", ".join(topics)

    def force_set_summary(self, new_summary: str):
        """
        Manually override the rolling summary (used during LLM summaries).
        """
        self.rolling_summary = new_summary

    def get_working_context(self) -> List[Dict[str, str]]:
        """
        Formats the current short-term state for the LLM prompt.
        """
        context = [{"role": "system", "content": self.system_instruction}]
        if self.rolling_summary:
            context.append({
                "role": "system",
                "content": f"[CONVERSATION SUMMARY HISTORY]\n{self.rolling_summary}\n[END SUMMARY HISTORY]"
            })
        for msg in self.messages:
            context.append({"role": msg["role"], "content": msg["content"]})
        return context

    def clear(self):
        self.messages = []
        self.rolling_summary = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": self.messages,
            "rolling_summary": self.rolling_summary,
            "system_instruction": self.system_instruction,
            "estimated_tokens": self.get_total_tokens()
        }
