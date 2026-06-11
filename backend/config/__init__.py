"""Configuration package."""
import os
from pathlib import Path

from dotenv import load_dotenv

from config.settings import get_settings, Settings
from config.logging import setup_logging, get_logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "backend/vectorstore/faiss_index")
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "backend/knowledge_base")

__all__ = [
    "get_settings",
    "Settings",
    "setup_logging",
    "get_logger",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "VECTORSTORE_PATH",
    "KNOWLEDGE_BASE_PATH",
]
