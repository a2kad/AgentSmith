from __future__ import annotations

import hashlib

from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


class CodebaseIndexer:
    COLLECTION = "codebase"
    VECTOR_DIM = 3072  # text-embedding-3-large

    SPLITTERS = {
        ".py": RecursiveCharacterTextSplitter.from_language(
            Language.PYTHON, chunk_size=1500, chunk_overlap=200
        ),
        ".ts": RecursiveCharacterTextSplitter.from_language(
            Language.JS, chunk_size=1500, chunk_overlap=200
        ),
        ".go": RecursiveCharacterTextSplitter.from_language(
            Language.GO, chunk_size=1500, chunk_overlap=200
        ),
        ".md": RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100),
        "default": RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150),
    }

    def __init__(self, qdrant_url: str, embedder):
        self.client = QdrantClient(url=qdrant_url)
        self.embedder = embedder
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(
                    size=self.VECTOR_DIM,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
            )
            for field in ["file_path", "language", "commit_sha"]:
                self.client.create_payload_index(
                    collection_name=self.COLLECTION,
                    field_name=field,
                    field_schema="keyword",
                )

    async def index_commit(self, files_changed: dict[str, str], commit_sha: str):
        """Инкрементальное обновление — только изменённые файлы"""
        for file_path, file_content in files_changed.items():
            self.client.delete(
                collection_name=self.COLLECTION,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="file_path",
                            match=MatchValue(value=file_path),
                        )
                    ]
                ),
            )

            ext = "." + file_path.split(".")[-1] if "." in file_path else "default"
            splitter = self.SPLITTERS.get(ext, self.SPLITTERS["default"])
            chunks = splitter.split_text(file_content)

            if not chunks:
                continue

            embeddings = await self.embedder.aembed_documents(chunks)

            points = [
                PointStruct(
                    id=self._chunk_id(file_path, i),
                    vector=emb,
                    payload={
                        "file_path": file_path,
                        "chunk_index": i,
                        "content": chunk,
                        "commit_sha": commit_sha,
                        "language": ext.lstrip("."),
                        "content_hash": hashlib.sha256(chunk.encode()).hexdigest(),
                    },
                )
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
            ]

            self.client.upsert(collection_name=self.COLLECTION, points=points)

    async def search_relevant_code(
        self, query: str, top_k: int = 8, filter_language: str | None = None
    ) -> list[dict]:
        """RAG-поиск для агентов"""
        query_vector = await self.embedder.aembed_query(query)
        search_filter = None
        if filter_language:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="language", match=MatchValue(value=filter_language)
                    )
                ]
            )

        results = self.client.search(
            collection_name=self.COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )
        return [{"score": r.score, **r.payload} for r in results]

    @staticmethod
    def _chunk_id(file_path: str, idx: int) -> int:
        return int(hashlib.sha256(f"{file_path}:{idx}".encode()).hexdigest()[:16], 16)
