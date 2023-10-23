# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import contextlib
import json
import logging
import os
import shutil
import sys
import traceback
from collections import namedtuple
from configparser import ConfigParser
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pydash
from dotenv import load_dotenv
from tabulate import tabulate

from promptflow._sdk._utils import print_red_error, print_yellow_warning
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.utils import is_in_ci_pipeline
from promptflow.exceptions import ErrorTarget, PromptflowException, UserErrorException

AzureMLWorkspaceTriad = namedtuple("AzureMLWorkspace", ["subscription_id", "resource_group_name", "workspace_name"])

logger = logging.getLogger(__name__)


def _set_workspace_argument_for_subparsers(subparser, required=False):
    """Add workspace arguments to subparsers."""
    # Make these arguments optional so that user can use local azure cli context
    subparser.add_argument(
        "--subscription", required=required, type=str, help="Subscription id, required when pass run id."
    )
    subparser.add_argument(
        "--resource-group", "-g", required=required, type=str, help="Resource group name, required when pass run id."
    )
    subparser.add_argument(
        "--workspace-name", "-w", required=required, type=str, help="Workspace name, required when pass run id."
    )


def dump_connection_file(dot_env_file: str):
    for key in ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_BASE", "CHAT_DEPLOYMENT_NAME"]:
        if key not in os.environ:
            # skip dump connection file if not all required environment variables are set
            return

    connection_file_path = "./connection.json"
    os.environ["PROMPTFLOW_CONNECTIONS"] = connection_file_path

    load_dotenv(dot_env_file)
    connection_dict = {
        "custom_connection": {
            "type": "CustomConnection",
            "value": {
                "AZURE_OPENAI_API_KEY": os.environ["AZURE_OPENAI_API_KEY"],
                "AZURE_OPENAI_API_BASE": os.environ["AZURE_OPENAI_API_BASE"],
                "CHAT_DEPLOYMENT_NAME": os.environ["CHAT_DEPLOYMENT_NAME"],
            },
            "module": "promptflow.connections",
        }
    }
    with open(connection_file_path, "w") as f:
        json.dump(connection_dict, f)


def get_workspace_triad_from_local() -> AzureMLWorkspaceTriad:
    subscription_id = None
    resource_group_name = None
    workspace_name = None
    azure_config_path = Path.home() / ".azure"
    config_parser = ConfigParser()
    # subscription id
    with contextlib.suppress(Exception):
        config_parser.read_file(open(azure_config_path / "clouds.config"))
        subscription_id = config_parser["AzureCloud"]["subscription"]
    # resource group name & workspace name
    with contextlib.suppress(Exception):
        config_parser.read_file(open(azure_config_path / "config"))
        resource_group_name = config_parser["defaults"]["group"]
        workspace_name = config_parser["defaults"]["workspace"]
    return AzureMLWorkspaceTriad(subscription_id, resource_group_name, workspace_name)


def get_credentials_for_cli():
    """
    This function is part of mldesigner.dsl._dynamic_executor.DynamicExecutor._get_ml_client with
    some local imports.
    """
    from azure.ai.ml.identity import AzureMLOnBehalfOfCredential
    from azure.identity import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential

    # May return a different one if executing in local
    # credential priority: OBO > managed identity > default
    # check OBO via environment variable, the referenced code can be found from below search:
    # https://msdata.visualstudio.com/Vienna/_search?text=AZUREML_OBO_ENABLED&type=code&pageSize=25&filters=ProjectFilters%7BVienna%7D&action=contents
    if os.getenv(IdentityEnvironmentVariable.OBO_ENABLED_FLAG):
        logger.info("User identity is configured, use OBO credential.")
        return AzureMLOnBehalfOfCredential()
    elif client_id_from_env := os.getenv(
        IdentityEnvironmentVariable.DEFAULT_IDENTITY_CLIENT_ID
    ):
        # use managed identity when client id is available from environment variable.
        # reference code:
        # https://learn.microsoft.com/en-us/azure/machine-learning/how-to-identity-based-service-authentication?tabs=cli#compute-cluster
        logger.info("Use managed identity credential.")
        return ManagedIdentityCredential(client_id=client_id_from_env)
    elif is_in_ci_pipeline():
        # use managed identity when executing in CI pipeline.
        logger.info("Use azure cli credential.")
        return AzureCliCredential()
    else:
        # use default Azure credential to handle other cases.
        logger.info("Use default credential.")
        return DefaultAzureCredential()


def get_client_for_cli(*, subscription_id: str = None, resource_group_name: str = None, workspace_name: str = None):
    from azure.ai.ml import MLClient

    if not (subscription_id and resource_group_name and workspace_name):
        workspace_triad = get_workspace_triad_from_local()
        subscription_id = subscription_id or workspace_triad.subscription_id
        resource_group_name = resource_group_name or workspace_triad.resource_group_name
        workspace_name = workspace_name or workspace_triad.workspace_name

    if not (subscription_id and resource_group_name and workspace_name):
        workspace_name = workspace_name or os.getenv("AZUREML_ARM_WORKSPACE_NAME")
        subscription_id = subscription_id or os.getenv("AZUREML_ARM_SUBSCRIPTION")
        resource_group_name = resource_group_name or os.getenv("AZUREML_ARM_RESOURCEGROUP")

    if missing_fields := [
        key
        for key in ["workspace_name", "subscription_id", "resource_group_name"]
        if not locals()[key]
    ]:
        raise UserErrorException(
            f'Please provide all required fields to work on specific workspace: {", ".join(missing_fields)}',
            target=ErrorTarget.CONTROL_PLANE_SDK,
        )

    return MLClient(
        credential=get_credentials_for_cli(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )


def confirm(question) -> bool:
    answer = input(f"{question} [y/n]")
    while answer.lower() not in ["y", "n"]:
        answer = input("Please input 'y' or 'n':")
    return answer.lower() == "y"


@contextlib.contextmanager
def inject_sys_path(path):
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path = original_sys_path


def activate_action(name, description, epilog, add_params, subparsers, help_message, action_param_name="action"):
    parser = subparsers.add_parser(
        name,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=help_message,
    )
    if add_params:
        for add_param_func in add_params:
            add_param_func(parser)
    parser.set_defaults(**{action_param_name: name})
    return parser


class IdentityEnvironmentVariable:
    """This class is copied from mldesigner._constants.IdentityEnvironmentVariable."""

    DEFAULT_IDENTITY_CLIENT_ID = "DEFAULT_IDENTITY_CLIENT_ID"
    OBO_ENABLED_FLAG = "AZUREML_OBO_ENABLED"


def _dump_entity_with_warnings(entity) -> Dict:
    if not entity:
        return
    if isinstance(entity, Dict):
        return entity
    try:
        return entity._to_dict()  # type: ignore
    except Exception as err:
        logger.warning(f"Failed to deserialize response: {str(err)}")
        logger.warning(str(entity))
        logger.debug(traceback.format_exc())


def list_of_dict_to_dict(obj: list):
    if not isinstance(obj, list):
        return {}
    result = {}
    for item in obj:
        result.update(item)
    return result


def list_of_dict_to_nested_dict(obj: list):
    result = {}
    for item in obj:
        for keys, value in item.items():
            keys = keys.split(".")
            pydash.set_(result, keys, value)
    return result


def _build_sorted_column_widths_tuple_list(
    columns: List[str],
    values1: Dict[str, int],
    values2: Dict[str, int],
    margins: Dict[str, int],
) -> List[Tuple[str, int]]:
    res = [
        (column, max(values1[column], values2[column]) + margins[column])
        for column in columns
    ]
    res.sort(key=lambda x: x[1], reverse=True)
    return res


def _assign_available_width(
    column_expected_widths: List[Tuple[str, int]],
    available_width: int,
    column_assigned_widths: Dict[str, int],
    average_width: Optional[int] = None,
) -> Tuple[int, Dict[str, int]]:
    for column, expected_width in column_expected_widths:
        if available_width <= 0:
            break
        target = average_width if average_width is not None else column_assigned_widths[column]
        delta = expected_width - target
        if delta <= available_width:
            column_assigned_widths[column] = expected_width
            available_width -= delta
        else:
            column_assigned_widths[column] += available_width
            available_width = 0
    return available_width, column_assigned_widths


def _calculate_column_widths(df: pd.DataFrame, terminal_width: int) -> List[int]:
    num_rows, num_columns = len(df), len(df.columns)
    index_column_width = max(len(str(num_rows)) + 2, 4)  # tabulate index column min width is 4
    terminal_width_buffer = 10
    available_width = terminal_width - terminal_width_buffer - index_column_width - (num_columns + 2)
    avg_available_width = available_width // num_columns

    header_widths, content_avg_widths, content_max_widths, column_margin = {}, {}, {}, {}
    for column in df.columns:
        header_widths[column] = len(column)
        contents = [len(str(value)) for value in df[column]]
        content_avg_widths[column] = sum(contents) // len(contents)
        content_max_widths[column] = max(contents)
        # if header is longer than the longest content, the margin is 4; otherwise is 2
        # so we need to record this for every column
        if header_widths[column] >= content_max_widths[column]:
            column_margin[column] = 4
        else:
            column_margin[column] = 2

    column_widths = {}
    # first round: try to meet the average(or column header) width
    # record columns that need more width, we will deal with them in second round if we still have width
    round_one_left_columns = []
    for column in df.columns:
        expected_width = max(header_widths[column], content_avg_widths[column]) + column_margin[column]
        if avg_available_width <= expected_width:
            column_widths[column] = avg_available_width
            round_one_left_columns.append(column)
        else:
            column_widths[column] = expected_width

    current_available_width = available_width - sum(column_widths.values())
    if current_available_width > 0:
        # second round: assign left available width to those columns that need more
        # assign with greedy, sort recorded columns first from longest to shortest;
        # iterate and try to meet each column's expected width
        column_avg_tuples = _build_sorted_column_widths_tuple_list(
            round_one_left_columns, header_widths, content_avg_widths, column_margin
        )
        current_available_width, column_widths = _assign_available_width(
            column_avg_tuples, current_available_width, column_widths, avg_available_width
        )

    if current_available_width > 0:
        # third round: if there are still left available width, assign to try to meet the max width
        # still use greedy, sort first and iterate through all columns
        column_max_tuples = _build_sorted_column_widths_tuple_list(
            df.columns, header_widths, content_max_widths, column_margin
        )
        current_available_width, column_widths = _assign_available_width(
            column_max_tuples, current_available_width, column_widths
        )

    max_col_widths = [index_column_width]  # index column
    max_col_widths += [column_widths[column] - column_margin[column] for column in df.columns]  # sub margin
    return max_col_widths


def pretty_print_dataframe_as_table(df: pd.DataFrame) -> None:
    # try to get terminal window width
    try:
        terminal_width = shutil.get_terminal_size().columns
    except Exception:  # pylint: disable=broad-except
        terminal_width = 120  # default value for Windows Terminal launch size columns
    column_widths = _calculate_column_widths(df, terminal_width)
    print(tabulate(df, headers="keys", tablefmt="grid", maxcolwidths=column_widths, maxheadercolwidths=column_widths))


def is_format_exception():
    return (
        os.environ.get(
            "PROMPTFLOW_STRUCTURE_EXCEPTION_OUTPUT", "false"
        ).lower()
        == "true"
    )


def exception_handler(command: str):
    """Catch known cli exceptions."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if is_format_exception():
                    # When the flag format_exception is set in command,
                    # it will write a json with exception info and command to stderr.
                    error_msg = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
                    error_msg["command"] = " ".join(sys.argv)
                    sys.stderr.write(json.dumps(error_msg))
                if isinstance(e, PromptflowException):
                    print_red_error(f"{command} failed with {e.__class__.__name__}: {str(e)}")
                    exit(1)
                else:
                    raise e

        return wrapper

    return decorator


def get_secret_input(prompt, mask="*"):
    """Get secret input with mask printed on screen in CLI.

    Provide better handling for control characters:
    - Handle Ctrl-C as KeyboardInterrupt
    - Ignore control characters and print warning message.
    """
    if not isinstance(prompt, str):
        raise TypeError(f"prompt must be a str, not ${type(prompt).__name__}")
    if not isinstance(mask, str):
        raise TypeError(f"mask argument must be a one-character str, not ${type(mask).__name__}")
    if len(mask) != 1:
        raise ValueError("mask argument must be a one-character str")

    if sys.platform == "win32":
        # For some reason, mypy reports that msvcrt doesn't have getch, ignore this warning:
        from msvcrt import getch  # type: ignore
    else:  # macOS and Linux
        import termios
        import tty

        def getch():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch

    secret_input = []
    sys.stdout.write(prompt)
    sys.stdout.flush()

    while True:
        key = ord(getch())
        if key == 13:  # Enter key pressed.
            sys.stdout.write("\n")
            return "".join(secret_input)
        elif key == 3:  # Ctrl-C pressed.
            raise KeyboardInterrupt()
        elif key in {8, 127}:  # Backspace/Del key erases previous output.
            if len(secret_input) > 0:
                # Erases previous character.
                sys.stdout.write("\b \b")  # \b doesn't erase the character, it just moves the cursor back.
                sys.stdout.flush()
                secret_input = secret_input[:-1]
        elif 0 <= key <= 31:
            msg = "\nThe last user input got ignored as it is control character."
            print_yellow_warning(msg)
            sys.stdout.write(prompt + mask * len(secret_input))
            sys.stdout.flush()
        else:
            # display the mask character.
            char = chr(key)
            sys.stdout.write(mask)
            sys.stdout.flush()
            secret_input.append(char)
