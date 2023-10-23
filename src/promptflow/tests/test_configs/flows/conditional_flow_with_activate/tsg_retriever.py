from promptflow import tool


@tool
def tsg_retriever(content: str) -> str:
  return f"TSG: {content}"