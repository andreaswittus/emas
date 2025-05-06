# ========================= email_agents.py =========================
"""
rewriteagents.py — Specialist email rewrite agents
=================================================
Each agent rewrites an initial email draft to comply with department-specific
communication guidelines. Missing required details are replaced with clear
<<MISSING: ...>> placeholders.
"""

import abc
import textwrap
from .llm_client import LLMClient
from typing import Type, Dict


class EmailRewriteAgent(abc.ABC):
    """
    Abstract base for all email rewrite agents. Subclasses must set:
      - NAME: a topic key corresponding to the classifier
      - GUIDELINES: the prompt text with bullet points
    """

    NAME: str
    GUIDELINES: str

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def rewrite(self, draft: str) -> str:
        prompt = textwrap.dedent(f"""
            You are the **{self.NAME} helper**.

            GUIDELINES:
            {self.GUIDELINES}

            TASK:
            1. Rewrite the draft below so it meets every guideline.
            2. Insert <<MISSING: ...>> placeholders for any missing info.
            3. Return only the final email text (subject + body), no commentary.

            DRAFT:
            {draft}
        """)
        return self.llm.generate(prompt, temperature=0.3)


# ------------------ RMA Agent ------------------
SALES_SUPPORT_GUIDELINES = textwrap.dedent("""
Subject:
  • Must include a reference number (SO / RMA / Item / Batch).
  • Format example: "SO 31202516 - Fittings - Expected picking error".

BODY:
  • State whether the issue concerns *Fittings* or *Steel*.
  • Provide a concise description of the request or problem.
  • Include Sales Order #, Item #, Batch # when relevant.
  • If quantity mismatch: verify number of colli signed for and state result.
  • For "too much" material: ensure Sales has contacted Sales Support for return traceability.
  • Ask for attachments or reference screenshots; annotate when necessary.
  • Always communicate in English.
""")


class RMASupportAgent(EmailRewriteAgent):
    NAME = "rma"
    GUIDELINES = SALES_SUPPORT_GUIDELINES


# ------------------ Order Cancel Agent ------------------
ORDERCANCEL_GUIDELINES = textwrap.dedent("""
Subject:
  • Format: "<SO number> - <Order/Line Cancel> - <Reason>"
    e.g. "31548564 - Cancel Order - Wrong items".

BODY:
  • State the Sales Order number, if the order or lines should be cancelled.
  • Clearly describe the issue (delay, missing colli, damage, etc.).
  • If missing item or material: list Item #, dimensions, charge, quantity, colli #.
  • Keep language professional and concise.
""")


class CancelAgent(EmailRewriteAgent):
    NAME = "cancel"
    GUIDELINES = ORDERCANCEL_GUIDELINES


# ------------------ Change Route Agent ------------------
CHANGEROUTE_GUIDELINES = textwrap.dedent("""
Subject:
  • Format: "<SO number> - Route <##> - <Reason>"
    e.g. "31548564 - Route 50 - Missing colli".

BODY:
  • State the Sales Order number and route number.
  • Clearly describe the issue (delay, missing colli, damage, etc.).
  • If missing material: list Item #, dimensions, charge, quantity, colli #.
  • Keep language professional and concise.
""")


class ChangeRouteAgent(EmailRewriteAgent):
    NAME = "change route"
    GUIDELINES = CHANGEROUTE_GUIDELINES


# ------------- Agent registry ----------------
AGENT_REGISTRY: Dict[str, Type[EmailRewriteAgent]] = {
    RMASupportAgent.NAME: RMASupportAgent,
    CancelAgent.NAME: CancelAgent,
    ChangeRouteAgent.NAME: ChangeRouteAgent,
}


def get_agent(topic: str) -> Type[EmailRewriteAgent] | None:
    """Return the agent class for a given topic key, or None if not found."""
    return AGENT_REGISTRY.get(topic)


# ------------------------- 6. Demo usage -------------------------------
if __name__ == "__main__":
    # Example: refine a dummy draft for Sales Support
    sample_draft = (
        "Subject: Need help on order 31202516\n\n"
        "Hi team,\n"
        "Customer reports wrong item quantity.\n"
        "Thanks, Alice"
    )
    client = LLMClient()
    agent_class = get_agent("sales_support")
    agent = agent_class(client)
    print(agent.rewrite(sample_draft))
