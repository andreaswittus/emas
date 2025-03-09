"""Parts of the graph that require human input (human-in-the-loop)."""

import uuid

from langsmith import traceable
from eaia.schemas import State, email_template
from langgraph.types import interrupt
from langgraph.store.base import BaseStore
from typing import TypedDict, Literal, Union, Optional
from langgraph_sdk import get_client
from eaia.main.config import get_config

LGC = get_client()


class HumanInterruptConfig(TypedDict):
    allow_ignore: bool
    allow_respond: bool
    allow_edit: bool
    allow_accept: bool


class ActionRequest(TypedDict):
    action: str
    args: dict


class HumanInterrupt(TypedDict):
    action_request: ActionRequest
    config: HumanInterruptConfig
    description: Optional[str]


class HumanResponse(TypedDict):
    # The user’s choice: accept, ignore, provide a response, or edit
    type: Literal["accept", "ignore", "response", "edit"]
    args: Union[None, str, ActionRequest]


TEMPLATE = """# {subject}

[Click here to view the email]({url})

**To**: {to}
**From**: {_from}

{page_content}
"""


def _generate_email_markdown(state: State):
    """
    Build a Markdown snippet linking to the email and showing the subject, to, from, etc.
    """
    contents = state["email"]
    return TEMPLATE.format(
        subject=contents["subject"],
        url=f"https://mail.google.com/mail/u/0/#inbox/{contents['id']}",  # or Outlook link
        to=contents["to_email"],
        _from=contents["from_email"],
        page_content=contents["page_content"],
    )


async def save_email(state: State, config, store: BaseStore, status: str):
    """
    Save the email's triage outcome ('email', 'no', etc.) to the store for future examples or reflection.
    """
    namespace = (
        config["configurable"].get("assistant_id", "default"),
        "triage_examples",
    )
    key = state["email"]["id"]
    response = await store.aget(namespace, key)
    if response is None:
        data = {"input": state["email"], "triage": status}
        await store.aput(namespace, str(uuid.uuid4()), data)


@traceable
async def send_message(state: State, config, store):
    """
    Called when the LLM calls the 'Question' tool, so the user can respond or ignore.
    """
    prompt_config = get_config(config)
    memory = prompt_config["memory"]
    user = prompt_config["name"]

    tool_call = state["messages"][-1].tool_calls[0]
    request: HumanInterrupt = {
        "action_request": {"action": tool_call["name"], "args": tool_call["args"]},
        "config": {
            "allow_ignore": True,
            "allow_respond": True,
            "allow_edit": False,
            "allow_accept": False,
        },
        "description": _generate_email_markdown(state),
    }
    # This 'interrupt' function calls a UI or CLI to get the user's choice:
    response = interrupt([request])[0]

    _email_template = email_template.format(
        email_thread=state["email"]["page_content"],
        author=state["email"]["from_email"],
        subject=state["email"]["subject"],
        to=state["email"].get("to_email", ""),
    )

    if response["type"] == "response":
        # The user provided some textual answer
        msg = {
            "type": "tool",
            "name": tool_call["name"],
            "content": response["args"],
            "tool_call_id": tool_call["id"],
        }
        if memory:
            # If memory is on, we store triage outcome and possibly do a reflection run
            await save_email(state, config, store, "email")
            rewrite_state = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Draft a response to this email:\n\n{_email_template}",
                    }
                ]
                + state["messages"],
                "feedback": f"{user} responded in this way: {response['args']}",
                "prompt_types": ["background"],  # Removed "calendar"
                "assistant_key": config["configurable"].get("assistant_id", "default"),
            }
            await LGC.runs.create(None, "multi_reflection_graph", input=rewrite_state)

    elif response["type"] == "ignore":
        # The user decided to ignore
        msg = {
            "role": "assistant",
            "content": "",
            "id": state["messages"][-1].id,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "name": "Ignore",
                    "args": {"ignore": True},
                }
            ],
        }
        if memory:
            await save_email(state, config, store, "no")
    else:
        raise ValueError(f"Unexpected response type: {response}")

    return {"messages": [msg]}


@traceable
async def send_email_draft(state: State, config, store):
    """
    Called when the LLM calls 'ResponseEmailDraft' or 'NewEmailDraft', letting the user
    see/edit/accept the draft or ignore it altogether.
    """
    prompt_config = get_config(config)
    memory = prompt_config["memory"]
    user = prompt_config["name"]

    tool_call = state["messages"][-1].tool_calls[0]
    request: HumanInterrupt = {
        "action_request": {"action": tool_call["name"], "args": tool_call["args"]},
        "config": {
            "allow_ignore": True,
            "allow_respond": True,
            "allow_edit": True,
            "allow_accept": True,
        },
        "description": _generate_email_markdown(state),
    }
    response = interrupt([request])[0]

    _email_template = email_template.format(
        email_thread=state["email"]["page_content"],
        author=state["email"]["from_email"],
        subject=state["email"]["subject"],
        to=state["email"].get("to_email", ""),
    )

    if response["type"] == "response":
        # The user typed some response text
        msg = {
            "type": "tool",
            "name": tool_call["name"],
            "content": f"Error, {user} interrupted and gave this feedback: {response['args']}",
            "tool_call_id": tool_call["id"],
        }
        if memory:
            await save_email(state, config, store, "email")
            rewrite_state = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Draft a response to this email:\n\n{_email_template}",
                    }
                ]
                + state["messages"],
                "feedback": f"Error, {user} interrupted and gave this feedback: {response['args']}",
                "prompt_types": ["tone", "email", "background"],  # Removed "calendar"
                "assistant_key": config["configurable"].get("assistant_id", "default"),
            }
            await LGC.runs.create(None, "multi_reflection_graph", input=rewrite_state)

    elif response["type"] == "ignore":
        # The user wants to ignore
        msg = {
            "role": "assistant",
            "content": "",
            "id": state["messages"][-1].id,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "name": "Ignore",
                    "args": {"ignore": True},
                }
            ],
        }
        if memory:
            await save_email(state, config, store, "no")

    elif response["type"] == "edit":
        # The user wants to manually edit the draft
        msg = {
            "role": "assistant",
            "content": state["messages"][-1].content,
            "id": state["messages"][-1].id,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "args": response["args"]["args"],
                }
            ],
        }
        if memory:
            corrected = response["args"]["args"]["content"]
            await save_email(state, config, store, "email")
            rewrite_state = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Draft a response to this email:\n\n{_email_template}",
                    },
                    {
                        "role": "assistant",
                        "content": state["messages"][-1].tool_calls[0]["args"][
                            "content"
                        ],
                    },
                ],
                "feedback": f"A better response would have been: {corrected}",
                "prompt_types": ["tone", "email", "background"],  # Removed "calendar"
                "assistant_key": config["configurable"].get("assistant_id", "default"),
            }
            await LGC.runs.create(None, "multi_reflection_graph", input=rewrite_state)

    elif response["type"] == "accept":
        # The user accepts the draft as-is
        if memory:
            await save_email(state, config, store, "email")
        return None  # Return None to indicate no new messages

    else:
        raise ValueError(f"Unexpected response type: {response}")

    return {"messages": [msg]}


@traceable
async def notify(state: State, config, store):
    """
    Called when the system wants to just 'notify' the user about an email
    without necessarily drafting a response.
    """
    prompt_config = get_config(config)
    memory = prompt_config["memory"]
    user = prompt_config["name"]

    request: HumanInterrupt = {
        "action_request": {"action": "Notify", "args": {}},
        "config": {
            "allow_ignore": True,
            "allow_respond": True,
            "allow_edit": False,
            "allow_accept": False,
        },
        "description": _generate_email_markdown(state),
    }
    response = interrupt([request])[0]

    _email_template = email_template.format(
        email_thread=state["email"]["page_content"],
        author=state["email"]["from_email"],
        subject=state["email"]["subject"],
        to=state["email"].get("to_email", ""),
    )

    if response["type"] == "response":
        # The user typed some instructions
        msg = {"type": "user", "content": response["args"]}
        if memory:
            await save_email(state, config, store, "email")
            rewrite_state = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Draft a response to this email:\n\n{_email_template}",
                    }
                ]
                + state["messages"],
                "feedback": f"{user} gave these instructions: {response['args']}",
                "prompt_types": ["email", "background"],  # Removed "calendar"
                "assistant_key": config["configurable"].get("assistant_id", "default"),
            }
            await LGC.runs.create(None, "multi_reflection_graph", input=rewrite_state)

    elif response["type"] == "ignore":
        # The user decided to ignore the notification
        msg = {
            "role": "assistant",
            "content": "",
            "id": str(uuid.uuid4()),
            "tool_calls": [
                {
                    "id": "foo",
                    "name": "Ignore",
                    "args": {"ignore": True},
                }
            ],
        }
        if memory:
            await save_email(state, config, store, "no")
    else:
        raise ValueError(f"Unexpected response type: {response}")

    return {"messages": [msg]}


# Helllooooo
# Removed send_cal_invite(...) entire function,
# since we are no longer dealing with calendar invites.
