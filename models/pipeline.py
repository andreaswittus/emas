# ========================= pipeline.py =========================
"""
pipeline.py — End‑to‑end orchestration of the Multi‑Agent System
================================================================
This script ties together:
  1. LLMClient: unified LLM interface for OpenAI
  2. TopicExtractorAgent: classifies raw user input into a topic
  3. Specialist Email Agents: rewrite drafts per department guidelines
  4. SQLite logging via upsert_df_to_sql_table
"""

from __future__ import annotations

import argparse
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd

from .llm_client import LLMClient
from .topic_agent import extract_topic
from .rewriteagents import get_agent
from data.etl.utils import upsert_df_to_sql_table

EMAIL_TABLE = "email_logs"


# ----------------------------------------------------------------------
def log_stage(stage: str, content: str, meta: Dict[str, Any]) -> None:
    """Append one processing stage to the SQLite email_logs table."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "content": content,
        **meta,
    }
    upsert_df_to_sql_table(EMAIL_TABLE, pd.DataFrame([record]))


# ----------------------------------------------------------------------
def process_email(
    user_input: str,
    client: LLMClient,
    topic_override: str | None = None,  # ← NEW: let the UI override the topic
) -> str:
    """
    Full MAS flow for one piece of user input.

    Args
    ----
    user_input : str
        Raw notes or incoming email text.
    client : LLMClient
        Wrapper around the OpenAI ChatCompletion endpoint.
    topic_override : str | None, optional
        If provided, skip the LLM classifier and force this topic label.
        Default is None (auto‑detect with `extract_topic`).

    Returns
    -------
    str
        The refined, department‑compliant email draft.
    """
    # 1 ▶ choose topic
    topic = topic_override or extract_topic(user_input)
    log_stage("topic_detected", topic, {"raw_input": user_input})

    # 2 ▶ initial generic draft
    init_prompt = textwrap.dedent(
        f"""
        You are an email assistant. Write a polite, professional draft in English
        based on the user's request below:

        {user_input}
        """
    )
    draft = client.generate(init_prompt)
    log_stage("initial_draft", draft, {"topic": topic})

    # 3 ▶ department‑specific rewrite (if we have a specialist agent)
    agent_cls = get_agent(topic)
    if not agent_cls:
        log_stage("no_agent_found", draft, {"topic": topic})
        return draft

    agent = agent_cls(client)
    refined = agent.rewrite(draft)
    log_stage("refined_draft", refined, {"topic": topic})

    return refined


# ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MAS email pipeline")
    parser.add_argument("prompt", help="Raw user request or notes for email drafting")
    parser.add_argument(
        "--topic",
        help="Optional manual topic override (sales_support, transport, complaint, other)",
        default=None,
    )
    args = parser.parse_args()

    llm_client = LLMClient()
    final_email = process_email(args.prompt, llm_client, topic_override=args.topic)

    separator = "=" * 80
    print(f"\n{separator}\n{final_email}\n{separator}\n")
