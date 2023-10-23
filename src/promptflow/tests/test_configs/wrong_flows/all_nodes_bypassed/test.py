from promptflow import tool


@tool
def test(text: str):
    return f"{text}hello world!"
