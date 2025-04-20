# ========================= pipeline.py =========================
"""
pipeline.py — End‑to‑end orchestration of the Multi‑Agent System
=================================================================
This script ties together:
  1. LLMClient: unified LLM interface for OpenAI
  2. TopicExtractorAgent: classifies raw user input into a topic
  3. Specialist Email Agents: rewrite drafts per department guidelines
  4. SQLite logging via upsert_df_to_sql_table
"""

from __future__ import annotations
import argparse
import textwrap
from typing import Any, Dict
from datetime import datetime, timezone
import pandas as pd

# models/pipeline.py
from .llm_client import LLMClient
from .topic_agent import extract_topic
from .rewriteagents import get_agent
from data.etl.utils import (
    upsert_df_to_sql_table,
)  # 1 level up (..), then down into data/etl


EMAIL_TABLE = "email_logs"


def log_stage(stage: str, content: str, meta: Dict[str, Any]):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "content": content,
        **meta,
    }
    df = pd.DataFrame([record])
    upsert_df_to_sql_table(EMAIL_TABLE, df)


def process_email(user_input: str, client: LLMClient) -> str:
    topic = extract_topic(user_input)
    log_stage("topic_detected", topic, {"raw_input": user_input})

    init_prompt = textwrap.dedent(f"""
        You are an email assistant. Write a polite, professional draft in English
        based on the user's request below:

        {user_input}
    """)
    draft = client.generate(init_prompt)
    log_stage("initial_draft", draft, {"topic": topic})

    agent_cls = get_agent(topic)
    if not agent_cls:
        log_stage("no_agent_found", draft, {"topic": topic})
        return draft

    agent = agent_cls(client)
    refined = agent.rewrite(draft)
    log_stage("refined_draft", refined, {"topic": topic})

    return refined


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MAS email pipeline")
    parser.add_argument("prompt", help="Raw user request or notes for email drafting")
    args = parser.parse_args()

    client = LLMClient()
    final_email = process_email(args.prompt, client)

    separator = "=" * 80
    print(f"\n{separator}\n{final_email}\n{separator}\n")
