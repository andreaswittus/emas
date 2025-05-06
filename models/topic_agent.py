# ========================= topic_agent.py =========================
"""
topic_agent.py — LLM‑powered topic extractor for inbound email requests
=============================================================================
This module defines a small agent that reads raw user input (an email request
or notes) and classifies it into one of several predefined topics so the main
pipeline can route to the appropriate department-specific email agent.

Key steps:
1. Load a taxonomy of allowed topics (with human-readable descriptions).
2. Build a clear, deterministic prompt for the LLM to choose one topic.
3. Parse the LLM's JSON response to extract the topic label.
4. Provide a convenience function `extract_topic` for pipeline use.
"""

# Standard library imports
import json
import textwrap
from typing import Dict, Any

# Import our common LLM client wrapper
from .llm_client import LLMClient, LLMError


# ------------------------- 1. Define the taxonomy -------------------------
# We list each topic key alongside a short description of when to use it.
TAXONOMY: Dict[str, str] = {
    "rma": (
        "Requests involving RMA, associated with rma, replacement order, ."
    ),
    "cancel": (
        "Requests involving order or line cancelation, associated with order cancellation, order please cancel, cancel line, cancel item"
    ),
    "change route": (
        "Requests involving route change, associated with change route, route change"
    ),
    "other": ("Anything else that does not fit the above categories."),
}


# -------------------- 2. TopicExtractorAgent class -------------------------
class TopicExtractorAgent:
    """
    Wraps an LLM call to classify text into one of our TAXONOMY labels.
    """

    def __init__(self, llm: LLMClient):
        # Save the LLM client instance for future calls
        self.llm = llm

    def __call__(self, text: str) -> str:
        """
        Given raw input text, returns the single best topic label.
        If parsing fails or label not recognized, defaults to 'other'.
        """
        # 2a. Construct a clear, structured prompt
        prompt = textwrap.dedent(f"""
            You are a classification assistant. Read the email or request below
            and assign it exactly one topic from the following list.

            TOPICS:
            {json.dumps(TAXONOMY, indent=2)}

            Respond ONLY with a JSON object like:
            {{ "topic": "<label>", "confidence": 0.00 }}
            Do not include any additional text, explanation, or formatting.

            EMAIL / NOTES:
            {text}
        """)

        try:
            # 2b. Ask the LLM to classify
            raw = self.llm.generate(prompt, temperature=0.0, max_tokens=60)

            # 2c. Parse the JSON response
            parsed: Any = json.loads(raw.strip())
            topic = parsed.get("topic", "other")

            # 2d. Validate against our taxonomy keys
            if topic not in TAXONOMY:
                return "other"
            return topic

        except (json.JSONDecodeError, KeyError, LLMError):
            # On any error (parsing, missing key, LLM failure), default to 'other'
            return "other"


# --------------- 3. Convenience function for pipeline ---------------------
def extract_topic(text: str) -> str:
    """
    Simple wrapper: create an LLMClient, instantiate the agent, and return the topic.
    Usage in pipeline: `topic = extract_topic(user_input)`
    """
    # Initialize LLM client (must have OPENAI_API_KEY set)
    client = LLMClient()

    # Create the agent and classify
    agent = TopicExtractorAgent(client)
    return agent(text)


# ----------------------- 4. Demo / CLI test block -------------------------
if __name__ == "__main__":
    # Quick manual test: run `python topic_agent.py` to see the output
    test_email = """
        Hi team,
        Our customer received the wrong batch of fittings on SO 31202516
        """
    print("Input text:\n", test_email)
    print("Detected topic:", extract_topic(test_email))
