from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from .db import init_db, add_message, get_recent_messages
from .chunker import make_chunks
from .vector_store import VectorStore
from .redact import redact_text


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    meta: Dict[str, Any]


class MemoryService:
    """
    Service untuk:
    1) simpan chat mentah ke SQLite
    2) bikin chunk dan index ke Chroma
    3) semantic search chat lama (ngulik)
    4) ambil recent messages untuk prompt
    """

    def __init__(self):
        init_db()
        self.vs = VectorStore()

    def save_user_message(self, conversation_id: str, text: str):
        add_message(conversation_id, "user", text)

    def save_assistant_message(self, conversation_id: str, text: str):
        add_message(conversation_id, "assistant", text)

    def get_recent(self, conversation_id: str, limit: int = 20) -> List[Dict[str, str]]:
        rows = get_recent_messages(conversation_id, limit=limit)
        # rows: (role, content, created_at)
        out = []
        for role, content, created_at in rows:
            out.append({"role": role, "content": content, "created_at": created_at})
        return out

    def _stable_chunk_id(self, conversation_id: str, chunk_text: str, chunk_index: int) -> str:
        # ID stabil supaya upsert tidak nambah duplikat
        h = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()[:12]
        return f"{conversation_id}_c{chunk_index}_{h}"

    def reindex_conversation(self, conversation_id: str, take_last_n_messages: int = 200):
        """
        Ambil N chat terakhir dari SQLite -> chunk -> redact -> upsert ke Chroma
        Pemula-friendly: reindex semua chunk dari N message terakhir.
        """
        rows = get_recent_messages(conversation_id, limit=take_last_n_messages)
        chunks = make_chunks(rows, max_chars=1500)

        for i, ch in enumerate(chunks):
            safe_text = redact_text(ch)
            chunk_id = self._stable_chunk_id(conversation_id, safe_text, i)
            self.vs.upsert_chunk(
                chunk_id=chunk_id,
                text=safe_text,
                metadata={
                    "conversation_id": conversation_id,
                    "chunk_index": i,
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            )

    def semantic_search(self, conversation_id: str, query: str, k: int = 5) -> List[RetrievedChunk]:
        hits = self.vs.search(query, k=k, where={"conversation_id": conversation_id})
        out: List[RetrievedChunk] = []
        for h in hits:
            out.append(RetrievedChunk(
                chunk_id=h["id"],
                text=h["text"],
                meta=h["meta"]
            ))
        return out

    def build_prompt_context(
        self,
        conversation_id: str,
        user_query: str,
        recent_limit: int = 16,
        memory_k: int = 4
    ) -> Dict[str, Any]:
        """
        Return paket context yang siap kamu injek ke prompt LLM:
        - recent messages
        - retrieved chunks (chat lama relevan)
        """
        recent = self.get_recent(conversation_id, limit=recent_limit)
        retrieved = self.semantic_search(conversation_id, user_query, k=memory_k)

        return {
            "recent": recent,
            "retrieved": [
                {"id": r.chunk_id, "text": r.text, "meta": r.meta}
                for r in retrieved
            ]
        }
