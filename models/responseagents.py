# ========================= email_agents.py =========================
"""
responseagents.py — Specialist email rewrite agents
=================================================
Each agent responds to initial email to ensure it complies with department-specific
communication guidelines. Missing required details are replaced with clear
<<MISSING: ...>> placeholders.
"""

import abc
import textwrap
from .llm_client import LLMClient
from typing import Type, Dict


class EmailResponseAgent(abc.ABC):
    """
    Abstract base for all email response agents. Subclasses must set:
      - NAME: a topic key corresponding to the classifier
      - GUIDELINES: the prompt text with bullet points
    """

    NAME: str
    GUIDELINES: str

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def respond(self, incoming_email: str) -> str:
        prompt = textwrap.dedent(f"""
            You are the **{self.NAME} response assistant**.

            GUIDELINES:
            {self.GUIDELINES}

            TASK:
            1. Read the incoming email below.
            2. Compose a professional response that:
            - Acknowledges the request.
            - Follows all the guidelines.
            - Clearly points out and politely requests any missing information (do not just insert placeholders).
            3. Return only the final email response (subject + body), no commentary.

            INCOMING EMAIL:
            {incoming_email}
        """)
        return self.llm.generate(prompt, temperature=0.3)

#--------------------------- RMA

RMA_RESPONS_GUIDELINES = textwrap.dedent("""
    Subject:
      • Must include a reference number (SO / RMA / Item / Batch).
      • Format example: "SO 31202516 - Fittings - Expected picking error".

    BODY:
      • Confirm whether the issue concerns *Fittings* or *Steel*.
      • Acknowledge the reported problem or request.
      • Ask clearly for any missing details (e.g. SO #, Item #, Batch #, quantity, photos).
      • If quantity mismatch: ask how many colli were signed for, and what was received.
      • If issue is “too much” material: confirm Sales has been contacted about traceability.
      • Ask for attachments or screenshots if needed; be specific.
      • Always communicate in English.
    """)

class RMAResponseAgent(EmailResponseAgent):
    NAME = "rma"
    GUIDELINES = RMA_RESPONS_GUIDELINES


#---------------------------- Cancellation
CANCELLATION_GUIDELINES = textwrap.dedent("""
Subject:
  • Format: "<SO number> - <Order/Line Cancel> - <Reason>"
    e.g. "31548564 - Cancel Order - Wrong items".

BODY:
  • If the request clearly states that the entire order should be cancelled (e.g. “Cancel Order”), acknowledge and confirm the cancellation. Do not ask about line-level details.
  • Only request additional details (Item #, dimensions, etc.) if the message clearly refers to cancelling specific lines.
  • Never include fallback language or clarifications if the full order cancellation is unambiguous.
  • Do not request details already included.
  • Always respond concisely and professionally.
""")

class CancelResponseAgent(EmailResponseAgent):
    NAME = "cancel"
    GUIDELINES = CANCELLATION_GUIDELINES


#---------------------------- Change Route
CHANGEROUTE_GUIDELINESGUIDELINES = textwrap.dedent("""
    Subject:
      • Format: "<SO number> - Route <##> - <Reason>"
        e.g. "31548564 - Route 50 - Missing colli".

    BODY:
      • Confirm the Sales Order number and requested route number.
      • Acknowledge the issue (delay, missing colli, damage, etc.).
      • If all relevant information is included (SO #, route #, reason):
          – Confirm the route change has been initiated or completed.
      • If any required details are missing:
          – Politely request the missing information (e.g., Item #, dimensions, quantity, colli #).
      • Keep the message professional and concise.
    """)

class ChangeRouteResponseAgent(EmailResponseAgent):
    NAME = "change route"
    GUIDELINES = CHANGEROUTE_GUIDELINESGUIDELINES

# ------------- Agent registry ----------------
AGENT_REGISTRY: Dict[str, Type[EmailResponseAgent]] = {
    RMAResponseAgent.NAME: RMAResponseAgent,
    CancelResponseAgent.NAME: CancelResponseAgent,
    ChangeRouteResponseAgent.NAME: ChangeRouteResponseAgent,
}


def get_responseagent(topic: str) -> Type[EmailResponseAgent] | None:
    """Return the agent class for a given topic key, or None if not found."""
    return AGENT_REGISTRY.get(topic)


# ------------------------- 6. Demo usage -------------------------------
# if __name__ == "__main__":
#     # Example: refine a dummy draft for Sales Support
#     sample_draft = (
#         "Subject: Fittingorder 31640370\n\n"
#         "Goodmorning Andreas, can you please cancel item ar25225360 from so 31640370? \n"
#         "Best Regards Lukas"
#     )
#     client = LLMClient()
#     agent_class = get_responseagent("CancelResponseAgent")
#     agent = agent_class(client)
#     print(agent.rewrite(sample_draft))