from api.schemas import CopilotRequest, CopilotResponse
from services.context_builder import build_context
from services.groq_service import generate_answer
from services.prompt_service import build_prompt
from services.rag_service import get_relevant_context


def build_analytics_response(request: CopilotRequest) -> CopilotResponse:
    documents = get_relevant_context(request.question)
    context = build_context(request.report_context, documents)
    prompt = build_prompt(request.question, context)
    answer = generate_answer(prompt)
    return CopilotResponse(answer=answer, sources=documents)
