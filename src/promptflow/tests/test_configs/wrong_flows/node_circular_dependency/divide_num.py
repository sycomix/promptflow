from promptflow import tool


@tool
def divide_num(num: int) -> int:
    return num // 2
