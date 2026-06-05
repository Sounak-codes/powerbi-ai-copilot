from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL


def generate_answer(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Groq API key is not configured."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        return f"Groq request failed: {exc}"
