"""
Document chunking strategies for RAG ingestion.

Splits documents into appropriately-sized chunks for embedding
and retrieval, with overlap to maintain context across boundaries.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class Chunk:
    """A document chunk ready for embedding."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_char: int = 0
    end_char: int = 0
    chunk_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "chunk_index": self.chunk_index,
        }


class DocumentChunker:
    """
    Split documents into chunks for embedding and retrieval.

    Supports multiple strategies:
    - fixed_size: Split by character count with overlap
    - sentence: Split on sentence boundaries
    - paragraph: Split on paragraph boundaries
    - semantic: Split based on topic shifts (requires more processing)
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        strategy: str = "sentence",
    ):
        self.chunk_size = chunk_size or settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or settings.rag_chunk_overlap
        self.strategy = strategy

    def chunk_document(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk a document into pieces.

        Args:
            text: Full document text.
            document_id: Source document ID.
            metadata: Document-level metadata to attach to each chunk.

        Returns:
            List of Chunk objects.
        """
        if not text or not text.strip():
            return []

        if self.strategy == "paragraph":
            chunks = self._chunk_by_paragraph(text)
        elif self.strategy == "sentence":
            chunks = self._chunk_by_sentence(text)
        else:
            chunks = self._chunk_fixed_size(text)

        # Build chunk objects
        result = []
        base_metadata = metadata or {}

        for i, (chunk_text, start, end) in enumerate(chunks):
            chunk = Chunk(
                chunk_id=f"{document_id}_chunk_{i}",
                text=chunk_text.strip(),
                metadata={
                    **base_metadata,
                    "document_id": document_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
                start_char=start,
                end_char=end,
                chunk_index=i,
            )
            result.append(chunk)

        logger.debug(f"Chunked document {document_id}: {len(result)} chunks")
        return result

    def chunk_batch(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Chunk]:
        """
        Chunk multiple documents.

        Args:
            documents: List of dicts with "id", "text", and optional "metadata".

        Returns:
            Flat list of all chunks.
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(
                text=doc.get("text", ""),
                document_id=doc.get("id", "unknown"),
                metadata=doc.get("metadata"),
            )
            all_chunks.extend(chunks)

        logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} total chunks")
        return all_chunks

    def _chunk_fixed_size(self, text: str) -> List[tuple]:
        """Split text by fixed character count with overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            chunks.append((chunk_text, start, min(end, len(text))))

            # Move forward by (chunk_size - overlap)
            start += self.chunk_size - self.chunk_overlap

        return chunks

    def _chunk_by_sentence(self, text: str) -> List[tuple]:
        """Split text into chunks at sentence boundaries."""
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        char_pos = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_length + sentence_len > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))

                # Overlap: keep last few sentences
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_len += len(s)

                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in current_chunk)
                chunk_start = char_pos - overlap_len

            current_chunk.append(sentence)
            current_length += sentence_len
            char_pos += sentence_len + 1  # +1 for space

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))

        return chunks

    def _chunk_by_paragraph(self, text: str) -> List[tuple]:
        """Split text into chunks at paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", text)
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        char_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                char_pos += 2
                continue

            para_len = len(para)

            if current_length + para_len > self.chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))

                # Start new chunk (paragraphs typically don't overlap)
                current_chunk = []
                current_length = 0
                chunk_start = char_pos

            current_chunk.append(para)
            current_length += para_len
            char_pos += para_len + 2

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))

        return chunks
