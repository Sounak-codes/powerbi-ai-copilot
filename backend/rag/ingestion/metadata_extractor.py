"""
Metadata extractor for enriching RAG documents.

Extracts and enriches metadata from various document types
to improve retrieval filtering and result quality.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import get_logger

logger = get_logger(__name__)


class MetadataExtractor:
    """
    Extract and enrich metadata from documents.

    Adds structured metadata for better filtering and retrieval.
    """

    def extract(
        self, text: str, source_type: str, base_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from document text and context.

        Args:
            text: Document text content.
            source_type: Type of source document.
            base_metadata: Pre-existing metadata to enrich.

        Returns:
            Enriched metadata dictionary.
        """
        metadata = base_metadata.copy() if base_metadata else {}

        metadata["source_type"] = source_type
        metadata["char_count"] = len(text)
        metadata["word_count"] = len(text.split())
        metadata["indexed_at"] = datetime.utcnow().isoformat()

        # Extract type-specific metadata
        if source_type == "dax_measure":
            metadata.update(self._extract_dax_metadata(text))
        elif source_type in ("report_page", "report_overview"):
            metadata.update(self._extract_report_metadata(text))
        elif source_type == "data_model":
            metadata.update(self._extract_model_metadata(text))

        # Extract general features
        metadata["has_numbers"] = any(c.isdigit() for c in text)
        metadata["has_code"] = "=" in text or "(" in text

        return metadata

    def _extract_dax_metadata(self, text: str) -> Dict[str, Any]:
        """Extract DAX-specific metadata."""
        import re

        metadata = {}

        # Detect complexity
        paren_depth = max(
            text[:i].count("(") - text[:i].count(")")
            for i in range(len(text))
        ) if text else 0
        metadata["nesting_depth"] = paren_depth

        if paren_depth > 5:
            metadata["complexity"] = "high"
        elif paren_depth > 2:
            metadata["complexity"] = "medium"
        else:
            metadata["complexity"] = "low"

        # Check for common patterns
        metadata["uses_variables"] = "VAR " in text.upper()
        metadata["uses_calculate"] = "CALCULATE" in text.upper()
        metadata["uses_time_intel"] = any(
            f in text.upper()
            for f in ("DATEADD", "SAMEPERIODLASTYEAR", "DATESYTD", "TOTALYTD")
        )

        return metadata

    def _extract_report_metadata(self, text: str) -> Dict[str, Any]:
        """Extract report page metadata."""
        import re

        metadata = {}

        # Count visuals mentioned
        visual_types = ["chart", "table", "card", "map", "gauge", "slicer"]
        metadata["visual_types_mentioned"] = [
            vt for vt in visual_types if vt.lower() in text.lower()
        ]

        return metadata

    def _extract_model_metadata(self, text: str) -> Dict[str, Any]:
        """Extract data model metadata."""
        import re

        metadata = {}

        # Count columns and measures
        columns = re.findall(r"Columns?:\s*(.+)", text)
        if columns:
            col_text = columns[0]
            metadata["column_count"] = col_text.count(",") + 1

        measures = re.findall(r"Measures?:\s*(.+)", text)
        if measures:
            metadata["has_measures"] = True

        return metadata
