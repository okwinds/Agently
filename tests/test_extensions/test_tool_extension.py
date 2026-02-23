import pytest
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import os
import asyncio
import socket
from urllib.parse import urlparse
import time
from agently import Agently


def _ollama_available(base_url: str) -> bool:
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def test_tool_extension():
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    if not _ollama_available(base_url):
        pytest.skip(f"Ollama not available at {base_url}")

    Agently.set_settings(
        "OpenAICompatible",
        {
            "base_url": base_url,
            "model": "qwen2.5:7b",
            "model_type": "chat",
        },
    )

    agent = Agently.create_agent()

    @agent.tool_func
    async def add(a: int, b: int) -> int:
        """
        Get result of `a(int)` add `b(int)`
        """
        await asyncio.sleep(1)
        assert a == 34643523
        return a + b

    result = (
        agent.input("34643523+52131231=? Use tool to calculate!")
        .use_tool(add)
        .output(
            {
                "result": (int,),
            }
        )
        .start()
    )
    assert result["result"] == 86774754
