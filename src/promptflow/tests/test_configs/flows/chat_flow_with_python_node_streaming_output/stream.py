from promptflow import tool
from typing import Generator


def stream(question: str) -> Generator[str, None, None]:
    yield from question


@tool
def my_python_tool(chat_history: list[dict], question: str) -> dict:
    return {"answer": stream(question)}
