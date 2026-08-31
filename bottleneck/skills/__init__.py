"""Modular agent memory skills reverse engineered from widemem-ai.
"""

from bottleneck.skills.sanitizer import sanitize, detect_injection
from bottleneck.skills.decay import compute_recency_score
from bottleneck.skills.ymyl import classify_ymyl, classify_ymyl_detailed, is_ymyl, is_ymyl_strong
from bottleneck.skills.uncertainty import (
    assess_confidence,
    detect_frustration,
    extract_forgotten_fact,
    build_uncertainty_guidance,
    build_frustration_response,
)
from bottleneck.skills.active import Clarification, ActiveRetrieval
