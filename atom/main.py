import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, cast

from crawl4ai import RegexChunking
from dotenv import load_dotenv
from openai import AsyncOpenAI

from supabase import Client, create_client

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase_client: Client = create_client(
    supabase_url=cast(str, os.getenv("SUPABASE_URL")),
    supabase_key=cast(str, os.getenv("SUPABASE_SERVICE_KEY")),
)


@dataclass
class ProcessedChunk:
    name: str
    summary: str
    chunk_index: int
    content: str
    embedding: List[float]
    metadata: Dict[str, str]


async def get_summary(content: str) -> str:
    developer_prompt = """You are an expert at summarizing content from Swift type documentation and code examples:
    Return the concise summary.
    """
    try:
        response = await openai_client.chat.completions.create(
            model=os.getenv("MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": content},
            ],
        )
        if response and response.choices:
            return response.choices[0].message.content.strip()
        else:
            print(f"No response when trying to summarize content")
            return ""
    except Exception as e:
        print(f"Failed to get content summary: {e}")
        return f"Error summarizing content"


async def get_embedding(content: str) -> List[float]:
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small", input=content
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Failed to get embedding: {e}")
        return [0] * 1536


async def process_chunks(name: str, file_path: str, content: str, idx: int):
    summary = await get_summary(content)
    embedding = await get_embedding(content)
    metadata = {
        "source": "swiftui-atom-properties",
        "chunk_size": len(content),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_path": file_path,
    }
    return ProcessedChunk(
        name=name,
        summary=summary,
        chunk_index=idx,
        content=content,
        metadata=metadata,
        embedding=embedding,
    )


async def insert_chunk(chunk: ProcessedChunk):
    try:
        data = {
            "chunk_idx": chunk.chunk_index,
            "type_name": chunk.name,
            "summary": chunk.summary,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "embedding": chunk.embedding,
        }
        result = supabase_client.table("code_pages").insert(data).execute()
        print(f"Inserted chunk - {chunk.chunk_index}: {chunk.name}")
        return result
    except Exception as e:
        print(f"Failed to insert chunk: {e}")
        return None


async def chunk_code(content: str):
    """
    Just testing markdown splitting....
    This chunking is unnesessary in this case since we are getting the contents of files. We should just get the contents of the files directly.
    """
    chunker = RegexChunking([r"````\n\n", r"```\n\n"])
    code_blocks = chunker.chunk(content)[1:]

    def clean_chunk(chunk) -> Tuple[str, str, str]:
        try:
            file_path_str, file_content = chunk.split("\n", 1)
            file_path = Path(file_path_str.lstrip("## "))
            file_name = file_path.stem
            file_content = file_content.split("\n", 2)[2]
            return file_name, str(file_path), file_content
        except ValueError:
            print(f"Chunk formatting incorrect: {chunk}")
            return "", "", chunk

    chunks = map(clean_chunk, code_blocks)

    tasks = [
        process_chunks(name, file_path, chunk_content, idx)
        for idx, (name, file_path, chunk_content) in enumerate(chunks)
    ]

    processed_chunks = await asyncio.gather(*tasks)

    insert_tasks = [insert_chunk(chunk) for chunk in processed_chunks]

    await asyncio.gather(*insert_tasks)


async def main():
    load_dotenv()
    print(f"Loading Content...")
    content = Path("input_data/result.markdown").read_text(encoding="utf-8")
    await chunk_code(content)


if __name__ == "__main__":
    asyncio.run(main())
