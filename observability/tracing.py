from __future__ import annotations

import os
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from langfuse import Langfuse
from langfuse.callback import CallbackHandler

from orchestration.state import AgentSharedState

T = TypeVar("T")


class Settings:
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")


settings = Settings()

langfuse = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


def trace_agent(agent_name: str):
    """Декоратор для автоматической трассировки каждого агента"""

    def decorator(func: Callable[..., Awaitable[T]]):
        @wraps(func)
        async def wrapper(state: AgentSharedState, *args: Any, **kwargs: Any) -> T:
            trace = langfuse.trace(
                name=f"agent.{agent_name}",
                metadata={
                    "task_id": state["task_id"],
                    "iteration": state["iteration_count"],
                    "phase": state["current_phase"],
                },
            )
            span = trace.span(name=f"{agent_name}.execution")
            try:
                result = await func(
                    state,
                    *args,
                    **kwargs,
                    langfuse_handler=CallbackHandler(trace=trace),
                )
                if isinstance(result, dict):
                    span.end(output={"phase": result.get("current_phase")})
                else:
                    span.end()
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        return wrapper

    return decorator


# Использование
@trace_agent("security")
async def security_node(state: AgentSharedState, **kwargs: Any) -> AgentSharedState:
    raise NotImplementedError
