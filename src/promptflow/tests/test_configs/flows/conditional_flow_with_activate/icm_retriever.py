from promptflow import tool


@tool
def icm_retriever(content: str) -> str:
  return f"ICM: {content}"