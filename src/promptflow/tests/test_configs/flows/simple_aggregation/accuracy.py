from promptflow import tool, log_metric
from typing import List


@tool
def accuracy(answer: List[str], groundtruth: List[str]):
    assert isinstance(answer, list)
    correct = sum(1 for a, g in zip(answer, groundtruth) if a == g)
    accuracy = float(correct) / len(answer)
    log_metric("accuracy", accuracy)
    return accuracy
