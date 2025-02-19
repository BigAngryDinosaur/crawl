import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from supabase import Client

load_dotenv()

llm = os.getenv("MODEL", "gpt-4o-mini")
model = OpenAIModel(llm)


@dataclass
class Dependencies:
    supabase: Client
    openai_client: AsyncOpenAI


developer_prompt = """
You are an expert at SwiftUI Atom Properties: A State Management library for SwiftUI.
You have access to the source code of the library with documentation.

Your only job is to assist with this and you don't answer other questions besides describing what you are able to do.

Don't ask the user before taking an action, just do it. Always make sure you look at the source code with the provided tools before answering the user's question unless you have already.

When you first look at the documentation, always start with RAG.
Then also always check the list of available types and retrieve the source code if it'll help.

Always let the user know when you didn't find the answer  or the right Type - be honest.

"""

library_agent = Agent(
    model=model, system_prompt=developer_prompt, deps_type=Dependencies, retries=2
)


async def get_embedding(text: str, openai_client: AsyncOpenAI) -> List[float]:
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Failed to get embeddings: {e}")
        return [] * 1536


@library_agent.tool
async def get_code(ctx: RunContext[Dependencies], user_query: str) -> str:
    """
    Retrieve relevant Source Code chunks.

    Args:
        ctx: The context including Subabase and OpenAI clients
        user_query: The User's query

    Returns:
        str: A formatted string contaning the top 5 most relevant source code chunks
    """
    try:
        print(f"Fetching: {user_query}")
        query_embedding = get_embedding(user_query, ctx.deps.openai_client)

        result = ctx.deps.supabase.rpc(
            "match_code_pages",
            {
                "query_embedding": query_embedding,
                "match_count": 5,
                "filter": {"source": "swiftui-atom-properties"},
            },
        ).execute()

        if not result:
            return "No relevant source code found"

        formatted_chunks = []
        for source_code in result:
            chunk_text = """
            {source_code['type_name']}

            {source_code['content']}
            """
            formatted_chunks.append(chunk_text)

        return "\n\n---\n\n".join(formatted_chunks)

    except Exception as e:
        print(f"Failed to fetch Source code: {e}")
        return f"Error retrieving Source code: {str(e)}"


@library_agent.tool
async def get_type_names(ctx: RunContext[Dependencies]) -> List[str]:
    """
    Fetch a list of all the Swift Types available in the library

    Returns:
        List[str]: A list of Swift Type names
    """
    try:
        print(f"Fetching Types")
        result = (
            ctx.deps.supabase.from_("code_pages")
            .select("type_name")
            .eq("metadata->>source", "swiftui-atom-properties")
            .execute()
        )

        if not result:
            return []

        names = sorted(set(file["type_name"] for file in result.data))
        return names
    except Exception as e:
        print(f"Failed to retieve source code pages: {e}")
        return []


@library_agent.tool
async def get_code_for_type(ctx: RunContext[Dependencies], type_name: str) -> str:
    """
    Fetches the source code for a Swift Type

    Args:
        ctx: The Context including the Supabase client
        type_name: Name of the Swift Type

    Returns:
        str: The full source code of a Swift Type
    """
    try:
        print(f"Fetching Source Code for: {type_name}")
        result = (
            ctx.deps.supabase.from_("code_pages")
            .select("content, metadata->>file_path, chunk_idx")
            .eq("type_name", type_name)
            .eq("metadata->>source", "swiftui-atom-properties")
            .order("chunk_idx")
            .execute()
        )

        if not result:
            return f"No code found for Type: {type_name}"

        content = f"""
        File Path: {result.data[0]['file_path']}
        ```swift
        {result.data[0]['content']}
        ```
        """
        print(content)

        return content

    except Exception as e:
        print(f"Failed to retieve source code: {e}")
        return ""
