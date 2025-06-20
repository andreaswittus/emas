# ========================= pipeline.py =========================
"""
pipeline.py — End-to-end orchestration of the Multi-Agent System
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

# from .mistralClient import MistralClient --> removed from this script
from .llm_client import LLMClient
from .topic_agent import extract_topic
from .rewriteagents import get_agent
from .responseagents import get_responseagent
from data.etl.utils import upsert_df_to_sql_table

EMAIL_TABLE = "email_testset_logs"

# ----------------------------------------------------------------------


def log_email(log_data: Dict[str, Any]) -> None:
    """Insert one consolidated log row per processed email."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **log_data,
    }
    upsert_df_to_sql_table(EMAIL_TABLE, pd.DataFrame([record]))


def process_email(
    user_input: str,
    client: LLMClient,
    topic_override: str | None = None,
    mode: str = "draft",  # "draft" or "respond"
) -> str:
    """
    Email-processing pipeline that generates an initial draft in *both* modes
    and logs one consolidated row per email.
    """
    log_data: Dict[str, Any] = {
        "mode": mode,
        "raw_input": user_input,
        "detected_topic": None,
        "chosen_topic": None,
        "initial_draft": None,
        "final_output": None,
        "agent_found": True,
        "error": None,
    }

    try:
        # ▶ Detect and (optionally) override topic
        detected_topic = extract_topic(user_input)
        chosen_topic = topic_override or detected_topic
        log_data["detected_topic"] = detected_topic
        log_data["chosen_topic"] = chosen_topic

        # ──────────────────────────────────────────────────────────────
        # ▶ Generate an initial draft with the LLM in *both* modes
        # ──────────────────────────────────────────────────────────────
        if mode == "draft":
            init_prompt = textwrap.dedent(f"""
                You are an email assistant. Write a polite, professional **draft email**
                in English based on the user's request below:

                {user_input}
            """)
        else:  # mode == "respond"
            init_prompt = textwrap.dedent(f"""
                You are an email assistant. Write a polite, professional **reply**
                in English to the e-mail below:

                {user_input}
            """)

        initialoutput = client.generate(init_prompt)  # LLM call
        log_data["initial_draft"] = initialoutput  # ← always upserted

        # ──────────────────────────────────────────────────────────────
        # ▶ Choose the correct agent and produce the final version
        # ──────────────────────────────────────────────────────────────
        agent_cls = (
            get_agent(chosen_topic)
            if mode == "draft"
            else get_responseagent(chosen_topic)
        )
        if not agent_cls:
            log_data["agent_found"] = False
            log_data["final_output"] = initialoutput
            return initialoutput  # return early if no agent

        agent = agent_cls(client)
        if mode == "draft":
            final_output = agent.rewrite(initialoutput)  # refining the LLM draft
        else:  # respond
            final_output = agent.respond(initialoutput)  # refining the LLM reply

        log_data["final_output"] = final_output
        return final_output

    except Exception as e:
        log_data["error"] = str(e)
        raise

    finally:
        # One consolidated upsert per e-mail
        log_email(log_data)


# def process_email(
#     user_input: str,
#     client: MistralClient,
#     topic_override: str | None = None,
#     mode: str = "draft",  # "draft" or "respond"
# ) -> str:
#     """
#     Email processing pipeline supporting both drafting and response modes.
#     Logs only one row per email.
#     """
#     log_data = {
#         "mode": mode,
#         "raw_input": user_input,
#         "detected_topic": None,
#         "chosen_topic": None,
#         "initial_draft": None,
#         "final_output": None,
#         "agent_found": True,
#         "error": None,
#     }

#     try:
#         # ▶ Detect and choose topic
#         detected_topic = extract_topic(user_input)
#         chosen_topic = topic_override or detected_topic
#         log_data["detected_topic"] = detected_topic
#         log_data["chosen_topic"] = chosen_topic

#         # ▶ Generate initial draft if in draft mode
#         #        if mode == "draft":
#         init_prompt = textwrap.dedent(f"""
#             You are an email assistant. Write a polite, professional draft in English
#             based on the user's request below:

#         {user_input}
#             """)
#         draft = client.generate(init_prompt)
#         log_data["initial_draft"] = draft
#         #        else:
#         #            draft = user_input  # For "respond", use the incoming email

#         # ▶ Get appropriate agent
#         agent_cls = (
#             get_agent(chosen_topic)
#             if mode == "draft"
#             else get_responseagent(chosen_topic)
#         )
#         if not agent_cls:
#             log_data["agent_found"] = False
#             log_data["final_output"] = draft
#             return draft

#         agent = agent_cls(client)
#         final_output = agent.rewrite(draft) if mode == "draft" else agent.respond(draft)
#         log_data["final_output"] = final_output
#         return final_output

#     except Exception as e:
#         log_data["error"] = str(e)
#         raise

#     finally:
#         log_email(log_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MAS email pipeline")
    parser.add_argument("prompt", help="Raw user request or incoming email")
    parser.add_argument(
        "--topic",
        help="Optional manual topic override (e.g. rma, cancel, change route)",
        default=None,
    )
    parser.add_argument(
        "--mode",
        help="Operation mode: 'draft' (default) or 'respond'",
        choices=["draft", "respond"],
        default="draft",
    )

    args = parser.parse_args()
    llm_client = LLMClient()
    final_email = process_email(
        args.prompt, llm_client, topic_override=args.topic, mode=args.mode
    )

    separator = "=" * 80
    print(f"\n{separator}\n{final_email}\n{separator}\n")


# def log_stage(stage: str, content: str, meta: Dict[str, Any]) -> None:
#     """Append one processing stage to the SQLite email_logs table."""
#     record = {
#         "timestamp": datetime.now(timezone.utc).isoformat(),
#         "stage": stage,
#         "content": content,
#         **meta,
#     }
#     upsert_df_to_sql_table(EMAIL_TABLE, pd.DataFrame([record]))

# def process_email(
#     user_input: str,
#     client: LLMClient,
#     topic_override: str | None = None,
#     mode: str = "draft",  # NEW: "draft" or "respond"
# ) -> str:
#     """
#     Email processing pipeline supporting both drafting and response modes.
#     """
#     # 1 ▶ choose topic
#     topic = topic_override or extract_topic(user_input)
#     log_stage("topic_detected", topic, {"raw_input": user_input, "mode": mode})

#     # 2 ▶ initial generic draft/acknowledgement (optional for rewrite mode)
#     if mode == "draft":
#         init_prompt = textwrap.dedent(
#             f"""
#             You are an email assistant. Write a polite, professional draft in English
#             based on the user's request below:

#             {user_input}
#             """
#         )
#         draft = client.generate(init_prompt)
#         log_stage("initial_draft", draft, {"topic": topic})
#     else:
#         draft = user_input  # in "respond" mode, treat input as the incoming email

#     # 3 ▶ Choose appropriate agent
#     if mode == "draft":
#         agent_cls = get_agent(topic)
#     elif mode == "respond":
#         agent_cls = get_responseagent(topic)
#     else:
#         raise ValueError(f"Invalid mode: {mode}")

#     if not agent_cls:
#         log_stage("no_agent_found", draft, {"topic": topic, "mode": mode})
#         return draft

#     agent = agent_cls(client)
#     final_output = (
#         agent.rewrite(draft) if mode == "draft" else agent.respond(draft)
#     )

#     log_stage("refined_output", final_output, {"topic": topic, "mode": mode})
#     return final_output

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Run the MAS email pipeline")
#     parser.add_argument("prompt", help="Raw user request or incoming email")
#     parser.add_argument(
#         "--topic",
#         help="Optional manual topic override (e.g. rma, cancel, change route)",
#         default=None,
#     )
#     parser.add_argument(
#         "--mode",
#         help="Operation mode: 'draft' (default) or 'respond'",
#         choices=["draft", "respond"],
#         default="draft",
#     )

#     args = parser.parse_args()
#     llm_client = LLMClient()
#     final_email = process_email(
#         args.prompt, llm_client, topic_override=args.topic, mode=args.mode
#     )

#     separator = "=" * 80
#     print(f"\n{separator}\n{final_email}\n{separator}\n")


# ----------------------------------------------------------------------
# def process_email(
#     user_input: str,
#     client: LLMClient,
#     topic_override: str | None = None,  # ← NEW: let the UI override the topic
# ) -> str:
#     """
#     Full MAS flow for one piece of user input.

#     Args
#     ----
#     user_input : str
#         Raw notes or incoming email text.
#     client : LLMClient
#         Wrapper around the OpenAI ChatCompletion endpoint.
#     topic_override : str | None, optional
#         If provided, skip the LLM classifier and force this topic label.
#         Default is None (auto‑detect with `extract_topic`).

#     Returns
#     -------
#     str
#         The refined, department‑compliant email draft.
#     """
#     # 1 ▶ choose topic
#     topic = topic_override or extract_topic(user_input)
#     log_stage("topic_detected", topic, {"raw_input": user_input})

#     # 2 ▶ initial generic draft
#     init_prompt = textwrap.dedent(
#         f"""
#         You are an email assistant. Write a polite, professional draft in English
#         based on the user's request below:

#         {user_input}
#         """
#     )
#     draft = client.generate(init_prompt)
#     log_stage("initial_draft", draft, {"topic": topic})

#     # 3 ▶ department‑specific rewrite (if we have a specialist agent)
#     agent_cls = get_agent(topic)
#     if not agent_cls:
#         log_stage("no_agent_found", draft, {"topic": topic})
#         return draft

#     agent = agent_cls(client)
#     refined = agent.rewrite(draft)
#     log_stage("refined_draft", refined, {"topic": topic})

#     return refined


# # ----------------------------------------------------------------------
# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Run the MAS email pipeline")
#     parser.add_argument("prompt", help="Raw user request or notes for email drafting")
#     parser.add_argument(
#         "--topic",
#         help="Optional manual topic override (sales_support, transport, complaint, other)",
#         default=None,
#     )
#     args = parser.parse_args()

#     llm_client = LLMClient()
#     final_email = process_email(args.prompt, llm_client, topic_override=args.topic)

#     separator = "=" * 80
#     print(f"\n{separator}\n{final_email}\n{separator}\n")
