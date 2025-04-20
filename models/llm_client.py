# ========================= llm_client.py =========================
"""
llm_client.py — Wrapper around OpenAI ChatCompletion only
=========================================================
This simplified client exclusively uses the OpenAI API for all LLM calls.
It loads configuration from a `.env` file (wherever located) and exposes a
single `generate` method for downstream modules.
"""

import os
from dotenv import load_dotenv, find_dotenv
import openai

# Automatically locate and load the nearest .env file, if it exists
dotenv_file = find_dotenv()
if dotenv_file:
    load_dotenv(dotenv_file)


class LLMError(Exception):
    """Custom exception for missing config or API errors."""

    pass


class LLMClient:
    """
    Client that talks exclusively to OpenAI ChatCompletion.
    - Requires OPENAI_API_KEY in the environment (or in a .env file).
    - Optionally reads OPENAI_MODEL to override default (`gpt-4o-mini`).
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("Set OPENAI_API_KEY in environment or in a .env file.")
        openai.api_key = self.api_key

    def generate(
        self, prompt: str, temperature: float = 0.4, max_tokens: int = 512
    ) -> str:
        """Generate text from prompt using OpenAI ChatCompletion."""
        response = openai.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # response.choices[0].message is a ChatCompletionMessage object
        content = response.choices[0].message.content
        return content.strip()


if __name__ == "__main__":
    # Quick test for LLMClient connectivity
    import textwrap

    test_prompt = textwrap.dedent("""
        Simply write 'test worked'
    """)
    client = LLMClient()
    result = client.generate(test_prompt, temperature=0.2, max_tokens=60)
    print("Response from LLMClient:", result)
