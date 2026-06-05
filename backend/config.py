import os

from dotenv import load_dotenv


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "backend/vectorstore/faiss_index")
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "backend/knowledge_base")
