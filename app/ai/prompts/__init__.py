"""
This package contains the various prompt builder functions for the AI agent.

By importing the functions here, we can simplify imports in other parts of the application,
allowing `from app.ai.prompts import promise_score_weights_prompt`, etc.
"""

from app.ai.prompts.promise_score_weights import WEIGHTS_SCHEMA, promise_score_weights_prompt
from app.ai.prompts.quantitative_scores import SCORES_SCHEMA, quantitative_scores_prompt
from app.ai.prompts.stock_due_diligence import (
    DUE_DILIGENCE_SCHEMA,
    SENTIMENTS,
    stock_due_diligence_prompt,
)

# Defines the public API of this package
__all__ = [
    "DUE_DILIGENCE_SCHEMA",
    "SCORES_SCHEMA",
    "SENTIMENTS",
    "WEIGHTS_SCHEMA",
    "promise_score_weights_prompt",
    "quantitative_scores_prompt",
    "stock_due_diligence_prompt",
]
