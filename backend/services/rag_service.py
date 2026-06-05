from vectorstore.retriever import retrieve_relevant_documents


def get_relevant_context(question: str) -> list[str]:
    return retrieve_relevant_documents(question)
