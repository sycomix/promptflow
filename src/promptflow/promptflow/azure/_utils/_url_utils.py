# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re


class BulkRunURL:
    """Parser for a flow run URL."""

    REGEX_PATTERN = ".*prompts/flow/([^/]+)/([^/]+)/bulktest/([^/]+).*"
    RUN_URL_FORMAT = (
        "https://ml.azure.com/prompts/flow/{}/{}/bulktest/{}/details?wsid="
        "/subscriptions/{}/resourcegroups/{}/providers/Microsoft.MachineLearningServices/workspaces/{}"
    )

    def __init__(self, url: str):
        if url:
            if not (match := re.match(self.REGEX_PATTERN, url)):
                raise ValueError(f"Invalid flow run URL: {url}")
            self.experiment_id = match.group(1)
            self.flow_id = match.group(2)
            self.bulk_test_id = match.group(3)

    @classmethod
    def get_url(cls, experiment_id, flow_id, bulk_test_id, subscription_id, resource_group, workspace_name):
        return cls.RUN_URL_FORMAT.format(
            experiment_id, flow_id, bulk_test_id, subscription_id, resource_group, workspace_name
        )


class BulkRunId:
    """Parser for a flow run ID."""

    REGEX_PATTERN = "azureml://experiment/([^/]+)/flow/([^/]+)/bulktest/([^/]+)(/run/[^/]+)?"
    RUN_ID_FORMAT = "azureml://experiment/{}/flow/{}/bulktest/{}"

    def __init__(self, arm_id: str):
        if arm_id:
            if not (match := re.match(self.REGEX_PATTERN, arm_id)):
                raise ValueError(f"Invalid flow run ID: {arm_id}")
            self.experiment_id = match.group(1)
            self.flow_id = match.group(2)
            self.bulk_test_id = match.group(3)
            self.run_id = (
                match.group(4).split("/")[-1].strip()
                if len(match.groups()) > 3
                else None
            )

    @classmethod
    def get_url(cls, experiment_id, flow_id, bulk_test_id, *, run_id=None):
        arm_id = cls.RUN_ID_FORMAT.format(experiment_id, flow_id, bulk_test_id)
        if run_id:
            arm_id += f"/run/{run_id}"
        return arm_id
