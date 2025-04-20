"""Core agent responsible for drafting emails for DACAPO."""

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.store.base import BaseStore

from Old_agent_code.schemas import (
    State,
    NewEmailDraft,
    ResponseEmailDraft,
    Question,
    Ignore,
    email_template,
)
from models.config import get_config

# Customized instructions for DACAPO email responses.
EMAIL_WRITING_INSTRUCTIONS = """You are {full_name}'s executive assistant at DACAPO. 
You are a top-notch executive assistant who is expert at handling business correspondence for DACAPO.

Background:
{background}

{name} receives many emails from clients, partners, and internal stakeholders. 
Your job is to help {name} respond in a professional and concise manner. 
When drafting responses, you must ask for clarification if necessary using the `Question` tool. 
Do not insert placeholders for names, emails, or details – always obtain precise information from {name}.

If the email requires a reply, use the `ResponseEmailDraft` tool to generate a draft.
Always ensure that the drafted email sounds like it is coming directly from {name}.

{response_preferences}

Remember: your responses should be direct, factual, and maintain the DACAPO brand tone.
{random_preferences}"""

draft_prompt = """{instructions}

Remember to call a tool correctly! Use the specified tool names exactly.
Here is the email thread. Note that this is the full thread; pay special attention to the most recent email.

{email}"""


async def draft_response(state: State, config: RunnableConfig, store: BaseStore):
    """Draft a response to an email for DACAPO."""
    # Get the model configuration from the config.
    model = config["configurable"].get("model", "gpt-4o")
    llm = ChatOpenAI(
        model=model,
        temperature=0,
        parallel_tool_calls=False,
        tool_choice="required",
    )

    # For this task, we remove scheduling-related tools.
    tools = [
        NewEmailDraft,
        ResponseEmailDraft,
        Question,
    ]
    messages = state.get("messages") or []
    if len(messages) > 0:
        tools.append(Ignore)

    # Retrieve configuration for prompting.
    prompt_config = get_config(config)
    namespace = (config["configurable"].get("assistant_id", "default"),)

    # Retrieve background info ("random_preferences") from the store.
    key = "random_preferences"
    result = await store.aget(namespace, key)
    if result and "data" in result.value:
        random_preferences = result.value["data"]
    else:
        await store.aput(
            namespace, key, {"data": prompt_config["background_preferences"]}
        )
        random_preferences = prompt_config["background_preferences"]

    # Retrieve tone/style info ("response_preferences") from the store.
    key = "response_preferences"
    result = await store.aget(namespace, key)
    if result and "data" in result.value:
        response_preferences = result.value["data"]
    else:
        await store.aput(
            namespace, key, {"data": prompt_config["response_preferences"]}
        )
        response_preferences = prompt_config["response_preferences"]

    # Construct the final prompt instructions by filling in our DACAPO-specific context.
    _prompt = EMAIL_WRITING_INSTRUCTIONS.format(
        random_preferences=random_preferences,
        response_preferences=response_preferences,
        name=prompt_config["name"],
        full_name=prompt_config["full_name"],
        background=prompt_config["background"],
    )

    input_message = draft_prompt.format(
        instructions=_prompt,
        email=email_template.format(
            email_thread=state["email"]["page_content"],
            author=state["email"]["from_email"],
            subject=state["email"]["subject"],
            to=state["email"].get("to_email", ""),
        ),
    )

    # Bind the tools to the LLM model.
    model = llm.bind_tools(tools)
    messages = [{"role": "user", "content": input_message}] + messages

    # Try up to 5 times to get a valid tool call from the model.
    i = 0
    while i < 5:
        response = await model.ainvoke(messages)
        if len(response.tool_calls) != 1:
            i += 1
            messages.append(
                {"role": "user", "content": "Please call a valid tool call."}
            )
        else:
            break

    return {"draft": response, "messages": [response]}
