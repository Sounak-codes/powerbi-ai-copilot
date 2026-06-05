from pathlib import Path


def build_index(knowledge_base_path: str = "backend/knowledge_base") -> None:
    path = Path(knowledge_base_path)
    documents = [p.read_text(encoding="utf-8") for p in path.rglob("*") if p.is_file()]
    print(f"Loaded {len(documents)} knowledge base documents.")
