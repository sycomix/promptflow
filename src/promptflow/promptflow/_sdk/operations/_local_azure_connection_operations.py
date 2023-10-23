# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import re
from typing import List

from promptflow._sdk._constants import AZURE_WORKSPACE_REGEX_FORMAT, LOGGER_NAME, MAX_LIST_CLI_RESULTS
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk.entities._connection import _Connection
from promptflow._telemetry.activity import ActivityType, monitor_operation

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class LocalAzureConnectionOperations:
    def __init__(self, connection_provider):
        from azure.identity import DefaultAzureCredential

        from promptflow.azure._pf_client import PFClient as PFAzureClient

        subscription_id, resource_group, workspace_name = self._extract_workspace(connection_provider)
        self._pfazure_client = PFAzureClient(
            # TODO: disable interactive credential when starting as a service
            credential=DefaultAzureCredential(exclude_interactive_browser_credential=False),
            subscription_id=subscription_id,
            resource_group_name=resource_group,
            workspace_name=workspace_name,
        )

    @classmethod
    def _extract_workspace(cls, connection_provider):
        match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, connection_provider)
        if not match or len(match.groups()) != 5:
            raise ValueError(
                "Malformed connection provider string, expected azureml:/subscriptions/<subscription_id>/"
                "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
                f"workspaces/<workspace_name>, got {connection_provider}"
            )
        subscription_id = match.group(1)
        resource_group = match.group(3)
        workspace_name = match.group(5)
        return subscription_id, resource_group, workspace_name

    @monitor_operation(activity_name="pf.connections.azure.list", activity_type=ActivityType.PUBLICAPI)
    def list(
        self,
        max_results: int = MAX_LIST_CLI_RESULTS,
        all_results: bool = False,
    ) -> List[_Connection]:
        """List connections.

        :return: List of run objects.
        :rtype: List[~promptflow.sdk.entities._connection._Connection]
        """
        if max_results != MAX_LIST_CLI_RESULTS or all_results:
            logger.warning(
                "max_results and all_results are not supported for workspace connection and will be ignored."
            )
        return self._pfazure_client._connections.list()

    @monitor_operation(activity_name="pf.connections.azure.get", activity_type=ActivityType.PUBLICAPI)
    def get(self, name: str, **kwargs) -> _Connection:
        """Get a connection entity.

        :param name: Name of the connection.
        :type name: str
        :return: connection object retrieved from the database.
        :rtype: ~promptflow.sdk.entities._connection._Connection
        """
        if with_secrets := kwargs.get("with_secrets", False):
            return self._pfazure_client._arm_connections.get(name)
        return self._pfazure_client._connections.get(name)

    @monitor_operation(activity_name="pf.connections.azure.delete", activity_type=ActivityType.PUBLICAPI)
    def delete(self, name: str) -> None:
        """Delete a connection entity.

        :param name: Name of the connection.
        :type name: str
        """
        raise NotImplementedError(
            "Delete workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )

    @monitor_operation(activity_name="pf.connections.azure.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, connection: _Connection, **kwargs):
        """Create or update a connection.

        :param connection: Run object to create or update.
        :type connection: ~promptflow.sdk.entities._connection._Connection
        """
        raise NotImplementedError(
            "Create or update workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )
