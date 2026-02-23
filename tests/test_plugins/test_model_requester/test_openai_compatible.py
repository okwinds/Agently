import pytest

import os
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

import socket
from urllib.parse import urlparse

from typing import cast
from agently import Agently
from agently.utils import SerializableRuntimeDataNamespace
from agently.builtins.plugins.ModelRequester.OpenAICompatible import (
    OpenAICompatible,
    ModelRequesterSettings,
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


def _ollama_available(base_url: str) -> bool:
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


if not _ollama_available(OLLAMA_BASE_URL):
    pytest.skip(f"Ollama not available at {OLLAMA_BASE_URL}", allow_module_level=True)


@pytest.mark.asyncio
async def test_main():
    request_settings = cast(
        ModelRequesterSettings,
        SerializableRuntimeDataNamespace(Agently.settings, "plugins.ModelRequester.OpenAICompatible"),
    )
    request_settings["base_url"] = OLLAMA_BASE_URL
    request_settings["model"] = OLLAMA_MODEL
    request_settings["model_type"] = "chat"
    request_settings["auth"] = None
    prompt = Agently.create_prompt()

    openai_compatible = OpenAICompatible(
        prompt,
        Agently.settings,
    )

    try:
        prompt.set("input", "ni hao")
        request_data = openai_compatible.generate_request_data()
        request_response = openai_compatible.request_model(request_data)
        response = openai_compatible.broadcast_response(request_response)
        async for event, message in response:
            print(event, message)
    except Exception as e:
        raise e
