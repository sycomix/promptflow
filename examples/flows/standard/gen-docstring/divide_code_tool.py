from promptflow import tool
from divider import Divider


@tool
def divide_code(file_content: str):
    return Divider.divide_file(file_content)
