from promptflow import tool


@tool
def my_python_tool(input1: str) -> str:
    return f'hello {input1}'
