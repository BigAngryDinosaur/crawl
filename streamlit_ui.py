import asyncio
import os
from typing import Literal, TypedDict, cast

import streamlit as st
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.messages import (ModelRequest, ModelResponse, TextPart,
                                  UserPromptPart)

from atom.agent import Dependencies, library_agent
from supabase import Client

load_dotenv()

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase: Client = Client(
    cast(str, os.getenv("SUPABASE_URL")), cast(str, os.getenv("SUPABASE_SERVICE_KEY"))
)


class ChatMessage(TypedDict):
    """Format the messages sent to browser"""

    role: Literal["user", "model"]
    timestamp: str
    content: str


def display_message(part):
    if part.part_kind == "system-prompt":
        with st.chat_message("system"):
            st.markdown(f"**System**, {part.content}")

    elif part.part_kind == "user-prompt":
        with st.chat_message("user"):
            st.markdown(part.content)

    elif part.part_kind == "text":
        with st.chat_message("assistant"):
            st.markdown(part.content)


async def run_agent_with_streaming(user_input: str):

    deps = Dependencies(supabase=supabase, openai_client=openai_client)

    async with library_agent.run_stream(
        user_prompt=user_input,
        deps=deps,
        message_history=st.session_state.messages[:-1],
    ) as result:
        partial_text = ""
        message_placeholder = st.empty()

        async for chunk in result.stream_text(delta=True):
            partial_text += chunk
            message_placeholder.markdown(partial_text)

        filtered_messages = [
            msg
            for msg in result.new_messages()
            if not (
                hasattr(msg, "parts")
                and any(part.part_kind == "user-prompt" for part in msg.parts)
            )
        ]

        st.session_state.messages.extend(filtered_messages)

        st.session_state.messages.append(
            ModelResponse(parts=[TextPart(content=partial_text)])
        )


async def main():
    st.title("SwiftUI Atom Properties: Agent")
    st.write("Ask any question about the SwiftUI Atom Properties library")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        if isinstance(msg, ModelRequest) or isinstance(msg, ModelResponse):
            for part in msg.parts:
                display_message(part)

    user_input = st.chat_input("Ask you question here")

    if user_input:
        st.session_state.messages.append(
            ModelRequest(parts=[UserPromptPart(content=user_input)])
        )

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            await run_agent_with_streaming(user_input)


if __name__ == "__main__":
    asyncio.run(main())
