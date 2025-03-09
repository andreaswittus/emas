from typing import Annotated, List, Literal
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.graph.message import AnyMessage
from typing_extensions import TypedDict
from langgraph.graph import add_messages


class EmailData(TypedDict):
    id: str
    thread_id: str  # conversation id might rename for clarity
    from_email: str
    subject: str
    page_content: str  # here we store .body.content # might rename for clarity
    send_time: str  # potentially store receivedDateTime or sentDateTime
    to_email: str


class RespondTo(BaseModel):
    logic: str = Field(
        default="", description="logic on WHY the response choice is the way it is"
    )
    response: Literal["no", "email", "notify", "question"] = "no"


class ResponseEmailDraft(BaseModel):
    content: str
    new_recipients: List[str]


class NewEmailDraft(BaseModel):
    content: str
    recipients: List[str]


class ReWriteEmail(BaseModel):
    tone_logic: str = Field(
        description="Logic for what the tone of the rewritten email should be"
    )
    rewritten_content: str = Field(description="Content rewritten with the new tone")


class Question(BaseModel):
    content: str


class Ignore(BaseModel):
    ignore: bool


class MeetingAssistant(BaseModel):
    call: bool


class SendCalendarInvite(BaseModel):
    emails: List[str] = Field(
        description="List of emails to send the calendar invitation for. Do NOT make any emails up!"
    )
    title: str = Field(description="Name of the meeting")
    start_time: str = Field(description="Start time in `2024-07-01T14:00:00` format")
    end_time: str = Field(description="End time in `2024-07-01T14:00:00` format")


def convert_obj(o, m):
    if isinstance(m, dict):
        return RespondTo(**m)
    else:
        return m


class State(TypedDict):
    email: EmailData
    triage: Annotated[RespondTo, convert_obj]
    messages: Annotated[List[AnyMessage], add_messages]


email_template = """From: {from_email}
To: {to_email}
Subject: {subject}

{page_content}"""
