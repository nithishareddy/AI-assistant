from openai import AsyncOpenAI
from app.config import get_settings
from typing import AsyncIterator

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def chat_completion(messages: list[dict]) -> str:
    settings = get_settings()
    client = get_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


async def chat_completion_stream(messages: list[dict]) -> AsyncIterator[str]:
    settings = get_settings()
    client = get_client()
    stream = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.2,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
