from typing import List

from promptflow import log_metric, tool


@tool
def calculate_accuracy(grades: List[str]):
    result = list(grades)
    # calculate accuracy for each variant
    accuracy = round((result.count("Correct") / len(result)), 2)
    log_metric("accuracy", accuracy)

    return result
