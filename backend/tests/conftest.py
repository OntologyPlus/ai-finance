import asyncio
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_llm():
    with patch("utils.llm_client.get_llm_client") as mock:
        client = MagicMock()
        client._mock_mode = True
        client.invoke = AsyncMock(return_value=MagicMock(content="[Mock] 测试回复"))
        client.stream = MagicMock(return_value=iter(["[Mock] "]))
        client.bind_tools = MagicMock(return_value=client)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_memory():
    with patch("services.memory.MemoryManager") as mock:
        instance = MagicMock()
        instance.get_context = MagicMock(return_value="")
        instance.store = MagicMock()
        mock.return_value = instance
        yield instance
