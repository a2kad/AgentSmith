from __future__ import annotations

import asyncio
from typing import Optional

import redis.asyncio as aioredis
from anthropic import Anthropic


class TokenOptimizer:
    PRICING = {
        "claude-sonnet-4-5": {"input": 3.0, "output": 15.0, "cache_read": 0.30},
        "claude-haiku-4-5": {"input": 0.8, "output": 4.0, "cache_read": 0.08},
    }

    COMPACT_SYSTEM = (
        "Respond ONLY in JSON. No explanations outside JSON.\n"
        'Schema: {"action": str, "files": {path: content}, "reasoning": str (max 100 words)}'
    )

    def __init__(self, redis_client: aioredis.Redis, anthropic_client: Optional[Anthropic] = None, budget_prefix: str = "budget:"):
        self.redis = redis_client
        self.client = anthropic_client or Anthropic()
        self.budget_prefix = budget_prefix

    # 1. PROMPT CACHING — для system prompt и кодовой базы
    def build_cached_request(
        self, system_content: str, codebase_context: str, user_message: str, model: str = "claude-sonnet-4-5"
    ):
        return self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"Current codebase context:\n{codebase_context}",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[{"role": "user", "content": user_message}],
        )

    # 2. RATE LIMITING + BUDGET TRACKING
    async def track_and_limit(
        self,
        task_id: str,
        agent_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
        model: str,
    ) -> float:
        """Update budget atomically and raise if exceeded. Returns remaining budget."""
        p = self.PRICING.get(model, self.PRICING["claude-sonnet-4-5"])
        cost = (
            (max(prompt_tokens - cached_tokens, 0) / 1e6) * p["input"]
            + (completion_tokens / 1e6) * p["output"]
            + (cached_tokens / 1e6) * p["cache_read"]
        )

        budget_key = f"{self.budget_prefix}{task_id}"
        # Ensure key exists with a default (caller should set initial budget), but attempt atomic decrement
        remaining = await self.redis.incrbyfloat(budget_key, -cost)
        if remaining < 0:
            # rollback
            await self.redis.incrbyfloat(budget_key, cost)
            raise RuntimeError(f"Budget exceeded for task {task_id}; cost={cost:.8f}")
        return remaining

    # 3. MODEL ROUTING BASED ON TASK TYPE
    def route_model_for_task(self, task_type: str) -> str:
        routing = {
            "code_review_minor": "claude-haiku-4-5",
            "test_generation": "claude-haiku-4-5",
            "documentation": "claude-haiku-4-5",
            "architecture_design": "claude-sonnet-4-5",
            "security_audit": "claude-sonnet-4-5",
            "complex_refactoring": "claude-sonnet-4-5",
        }
        return routing.get(task_type, "claude-haiku-4-5")

    # 4. STRUCTURED OUTPUT вместо verbose prose — helper to prepend system
    def compact_system_prompt(self) -> str:
        return self.COMPACT_SYSTEM
