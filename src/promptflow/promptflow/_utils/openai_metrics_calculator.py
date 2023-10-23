import tiktoken

from promptflow.exceptions import UserErrorException


class OpenAIMetricsCalculator:
    def __init__(self, logger=None) -> None:
        self._logger = logger

    def get_openai_metrics_from_api_call(self, api_call: dict):
        total_metrics = {}
        if self._need_collect_metrics(api_call):
            try:
                metrics = self._get_openai_metrics_for_signal_api(api_call)
                self.merge_metrics_dict(total_metrics, metrics)
            except Exception as ex:
                self._log_warning(f"Failed to calculate metrics due to exception: {ex}.")

        children = api_call.get("children")
        if children is not None:
            for child in children:
                child_metrics = self.get_openai_metrics_from_api_call(child)
                self.merge_metrics_dict(total_metrics, child_metrics)

        return total_metrics

    def _need_collect_metrics(self, api_call: dict):
        if api_call.get("type") != "LLM":
            return False
        output = api_call.get("output")
        if not isinstance(output, dict) and not isinstance(output, list):
            return False
        inputs = api_call.get("inputs")
        return isinstance(inputs, dict)

    def _get_openai_metrics_for_signal_api(self, api_call: dict):
        output = api_call.get("output")
        if isinstance(output, dict):
            usage = output.get("usage")
            if isinstance(usage, dict):
                return usage
            self._log_warning(
                "Cannot find openai metrics in output, "
                "will calculate metrics from response data directly."
            )

        name = api_call.get("name")
        if name.split(".")[-2] == "ChatCompletion":
            return self._get_openai_metrics_for_chat_api(api_call)
        elif name.split(".")[-2] == "Completion":
            return self._get_openai_metrics_for_completion_api(api_call)
        else:
            raise CalculatingMetricsError(f"Calculating metrics for api {name} is not supported.")

    def _try_get_model(self, inputs):
        api_type = inputs.get("api_type")
        if not api_type:
            raise CalculatingMetricsError("Cannot calculate metrics for none or empty api_type.")
        model = inputs.get("engine") if api_type == "azure" else inputs.get("model")
        if not model:
            raise CalculatingMetricsError(
                "Cannot get a valid model to calculate metrics. "
                "Please specify a engine for AzureOpenAI API or a model for OpenAI API."
            )
        return model

    def _get_openai_metrics_for_chat_api(self, api_call):
        inputs = api_call.get("inputs")
        output = api_call.get("output")
        enc, tokens_per_message, tokens_per_name = self._get_encoding_for_chat_api(self._try_get_model(inputs))
        metrics = {
            "prompt_tokens": self._get_prompt_tokens_from_messages(
                inputs["messages"], enc, tokens_per_message, tokens_per_name
            )
        }
        if isinstance(output, list):
            metrics["completion_tokens"] = len(output)
        else:
            metrics["completion_tokens"] = self._get_completion_tokens_for_chat_api(output, enc)
        metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        return metrics

    def _get_encoding_for_chat_api(self, model):
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        if model == "gpt-35-turbo-0301":
            tokens_per_message = 4
            tokens_per_name = -1
        elif "gpt-35-turbo" in model or "gpt-3.5-turbo" in model or "gpt-4" in model:
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            raise CalculatingMetricsError(f"Calculating metrics for model {model} is not supported.")
        return enc, tokens_per_message, tokens_per_name

    def _get_prompt_tokens_from_messages(self, messages, enc, tokens_per_message, tokens_per_name):
        prompt_tokens = 0
        for message in messages:
            prompt_tokens += tokens_per_message
            for key, value in message.items():
                prompt_tokens += len(enc.encode(value))
                if key == "name":
                    prompt_tokens += tokens_per_name
        prompt_tokens += 3
        return prompt_tokens

    def _get_completion_tokens_for_chat_api(self, output, enc):
        completion_tokens = 0
        choices = output.get("choices")
        if isinstance(choices, list):
            for ch in choices:
                if isinstance(ch, dict):
                    message = ch.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str):
                            completion_tokens += len(enc.encode(content))
        return completion_tokens

    def _get_openai_metrics_for_completion_api(self, api_call: dict):
        inputs = api_call.get("inputs")
        output = api_call.get("output")
        enc = self._get_encoding_for_completion_api(self._try_get_model(inputs))
        metrics = {"prompt_tokens": 0}
        prompt = inputs.get("prompt")
        if isinstance(prompt, str):
            metrics["prompt_tokens"] = len(enc.encode(prompt))
        elif isinstance(prompt, list):
            for pro in prompt:
                metrics["prompt_tokens"] += len(enc.encode(pro))
        if isinstance(output, list):
            metrics["completion_tokens"] = len(output)
        else:
            metrics["completion_tokens"] = self._get_completion_tokens_for_completion_api(output, enc)
        metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        return metrics

    def _get_encoding_for_completion_api(self, model):
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("p50k_base")

    def _get_completion_tokens_for_completion_api(self, output, enc):
        completion_tokens = 0
        choices = output.get("choices")
        if isinstance(choices, list):
            for ch in choices:
                if isinstance(ch, dict):
                    text = ch.get("text")
                    if isinstance(text, str):
                        completion_tokens += len(enc.encode(text))
        return completion_tokens

    def merge_metrics_dict(self, metrics: dict, metrics_to_merge: dict):
        for k, v in metrics_to_merge.items():
            metrics[k] = metrics.get(k, 0) + v

    def _log_warning(self, msg):
        if self._logger:
            self._logger.warning(msg)


class CalculatingMetricsError(UserErrorException):
    """The exception that is raised when calculating metrics failed."""

    pass
