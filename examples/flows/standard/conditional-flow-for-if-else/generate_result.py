from promptflow import tool


@tool
def generate_result(llm_result="", default_result="") -> str:
    return llm_result if llm_result else default_result
