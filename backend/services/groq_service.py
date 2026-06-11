from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL

REQUEST_TIMEOUT_SECONDS = 20.0


def generate_answer(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Groq API key is not configured."

    try:
        client = Groq(api_key=GROQ_API_KEY, timeout=REQUEST_TIMEOUT_SECONDS)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700,
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        return f"Groq request failed: {exc}"
