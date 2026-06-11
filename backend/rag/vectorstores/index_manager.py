"""
Index manager for RAG vector store lifecycle.

Handles index creation, updates, versioning, and cleanup.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


class IndexManager:
    """
    Manage the lifecycle of RAG vector store indices.

    Handles:
    - Index creation from documents
    - Incremental updates
    - Index versioning
    - Cleanup of stale indices
    """

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or "vectorstore")
        self._indices: Dict[str, Any] = {}

    def create_index(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        embedding_service=None,
    ) -> Dict[str, Any]:
        """
        Create a new index from documents.

        Args:
            index_name: Name for the index.
            documents: Documents with "id", "text", "metadata".
            embedding_service: Optional embedding service instance.

        Returns:
            Index metadata.
        """
        from rag.vectorstores.faiss_store import FAISSStore
        from rag.ingestion.chunking import DocumentChunker

        # Chunk documents
        chunker = DocumentChunker()
        chunks = chunker.chunk_batch(documents)

        index_path = self.base_path / index_name
        store = FAISSStore(index_path=str(index_path))

        # Store reference (embedding happens later in async flow)
        self._indices[index_name] = {
            "store": store,
            "chunks": chunks,
            "created_at": datetime.utcnow().isoformat(),
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "status": "created",
        }

        logger.info(
            f"Index '{index_name}' created: {len(documents)} docs, {len(chunks)} chunks"
        )

        return {
            "index_name": index_name,
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "status": "created",
        }

    def get_index(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Get index info."""
        return self._indices.get(index_name)

    def list_indices(self) -> List[Dict[str, Any]]:
        """List all managed indices."""
        return [
            {"name": name, **{k: v for k, v in info.items() if k != "store" and k != "chunks"}}
            for name, info in self._indices.items()
        ]

    def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        if index_name in self._indices:
            del self._indices[index_name]
            logger.info(f"Deleted index '{index_name}'")
            return True
        return False
