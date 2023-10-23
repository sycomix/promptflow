from promptflow import tool


@tool
def kql_retriever(content: str) -> str:
  return f"KQL: {content}"