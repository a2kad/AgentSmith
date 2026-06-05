from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from orchestration.state import ArchitecturalDecision
from memory.codebase_indexer import CodebaseIndexer


class AgentMemoryManager:
    # === SHORT-TERM: Redis (TTL-based session memory) ===
    SHORT_TERM_TTL = 3600 * 4  # 4 часа — одна рабочая сессия

    def __init__(self, redis: aioredis.Redis, db: AsyncSession, indexer: CodebaseIndexer):
        self.redis = redis
        self.db = db
        self.indexer = indexer

    async def save_working_context(self, agent_id: str, task_id: str, context: dict):
        """Кратковременная память — рабочий контекст агента"""
        key = f"ctx:{agent_id}:{task_id}"
        await self.redis.setex(key, self.SHORT_TERM_TTL, json.dumps(context, default=str))

    async def get_working_context(self, agent_id: str, task_id: str) -> dict:
        raw = await self.redis.get(f"ctx:{agent_id}:{task_id}")
        if not raw:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def append_thought(self, agent_id: str, task_id: str, thought: str):
        """Chain-of-thought лог в Redis Stream для real-time UI"""
        await self.redis.xadd(
            f"thoughts:{task_id}",
            {"agent": agent_id, "thought": thought, "ts": datetime.utcnow().isoformat()},
            maxlen=1000,
        )

    # === LONG-TERM: PostgreSQL (архитектурные решения, паттерны) ===
    async def save_architectural_decision(
        self, decision: ArchitecturalDecision, task_id: str
    ):
        """ADR (Architecture Decision Record) — навсегда"""
        stmt = text(
            """
            INSERT INTO architectural_decisions
                (id, task_id, decision, rationale, affected_components,
                 approved_by, created_at)
            VALUES (:id, :task_id, :decision, :rationale, :affected_components,
                    :approved_by, NOW())
            ON CONFLICT (id) DO NOTHING
            """
        )
        await self.db.execute(
            stmt,
            {
                "id": decision["id"],
                "task_id": task_id,
                "decision": decision["decision"],
                "rationale": decision["rationale"],
                "affected_components": decision["affected_components"],
                "approved_by": decision["approved_by"],
            },
        )
        await self.db.commit()

    async def get_relevant_decisions(self, query: str, limit: int = 5) -> list[dict]:
        """Семантический поиск по ADR через pgvector"""
        query_emb = await self.indexer.embedder.aembed_query(query)
        stmt = text(
            """
            SELECT id, decision, rationale, affected_components,
                   1 - (embedding <-> CAST(:query_vector AS vector)) AS similarity
            FROM architectural_decisions
            WHERE 1 - (embedding <-> CAST(:query_vector AS vector)) > 0.75
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )
        result = await self.db.execute(stmt, {"query_vector": query_emb, "limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]

    async def compress_context_window(
        self, messages: list, max_tokens: int = 6000
    ) -> list:
        """Сжатие истории через summarization при переполнении окна"""
        total = sum(len(str(m.get("content", ""))) // 3 for m in messages)
        if total <= max_tokens:
            return messages

        preserved = messages[-20:]
        summary_text = "\n".join(str(m.get("content", "")) for m in messages[:-20])
        summary = {
            "role": "system",
            "content": (
                "Summary of earlier conversation:\n"
                f"{summary_text[:4000]}"
            ),
        }
        return [summary, *preserved]
