from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path("data/chroma")
EMBED_MODEL = "all-MiniLM-L6-v2"

class VectorStore:
    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        # Embedding model (local)
        self.embedder = SentenceTransformer(EMBED_MODEL)

        # ✅ Proper persistent client for Chroma 0.5.x
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))

        # Collection untuk menyimpan chat chunks
        self.col = self.client.get_or_create_collection("chat_chunks")

    def embed(self, texts):
        return self.embedder.encode(texts).tolist()

    def upsert_chunk(self, chunk_id: str, text: str, metadata: dict):
        emb = self.embed([text])[0]
        self.col.upsert(
            ids=[chunk_id],
            embeddings=[emb],
            documents=[text],
            metadatas=[metadata]
        )
        # ❌ Tidak perlu persist() di PersistentClient

    def search(self, query: str, k: int = 5, where: dict | None = None):
        qemb = self.embed([query])[0]
        res = self.col.query(
            query_embeddings=[qemb],
            n_results=k,
            where=where
        )
        out = []
        for i in range(len(res["ids"][0])):
            out.append({
                "id": res["ids"][0][i],
                "text": res["documents"][0][i],
                "meta": res["metadatas"][0][i]
            })
        return out
