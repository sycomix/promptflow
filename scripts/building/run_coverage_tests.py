import argparse
import os
from pathlib import Path

from utils import Color, run_command

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"{Color.RED}Test Coverage for Promptflow!{Color.END}"
        + "\n"
    )

    parser.add_argument("-p", required=True, nargs="+", help="The paths to calculate code coverage")
    parser.add_argument("-t", required=True, nargs="+", help="The path to the tests")
    parser.add_argument("-l", required=True, help="Location to run tests in")
    parser.add_argument(
        "-m",
        required=True,
        help="Pytest marker to identify the tests to run",
        default="all",
    )
    parser.add_argument("-n", help="Pytest number of process to run the tests", default="15")
    parser.add_argument(
        "--model-name",
        help="The model file name to run the tests",
        type=str,
        default="",
    )
    parser.add_argument("--timeout", help="Timeout for individual tests (seconds)", type=str, default="")
    parser.add_argument(
        "--coverage-config",
        help="The path of code coverage config file",
        type=str,
        default="",
    )
    parser.add_argument(
        "--disable-cov-branch",
        action="store_true",
        help="Whether to enable branch coverage calculation",
    )

    args = parser.parse_args()
    print(f"Working directory: {os.getcwd()}")
    print(f"Args.p: {str(args.p)}")
    print(f"Args.t: {str(args.t)}")
    print(f"Args.l: {str(args.l)}")
    print(f"Args.m: {str(args.m)}")
    print(f"Args.n: {str(args.n)}")
    print(f"Args.model-name: {str(args.model_name)}")
    print(f"Args.timeout: {str(args.timeout)}")
    print(f"Args.coverage-config: {str(args.coverage_config)}")
    print(f"Args.disable-cov-branch: {str(args.disable_cov_branch)}")

    test_paths_list = [str(Path(path).absolute()) for path in args.t]

    # display a list of all Python packages installed in the current Python environment
    run_command(["pip", "list"])
    run_command(["pip", "show", "promptflow", "promptflow-sdk"])

    pytest_command = ["pytest", "--junit-xml=test-results.xml"]
    pytest_command += test_paths_list
    if args.coverage_config:
        if args.p:
            cov_path_list = [f"--cov={path}" for path in args.p]
            pytest_command += cov_path_list
        if not args.disable_cov_branch:
            pytest_command += ["--cov-branch"]
        pytest_command += [  # noqa: W503
            "--cov-report=term",
            "--cov-report=html",
            "--cov-report=xml",
        ]
        pytest_command += [f"--cov-config={args.coverage_config}"]
    pytest_command += [
        "-n",
        args.n,
        "--dist",
        "loadgroup",
        "--log-level=info",
        "--log-format=%(asctime)s %(levelname)s %(message)s",
        "--log-date-format=[%Y-%m-%d %H:%M:%S]",
        "--durations=5",
        "-ra",
        "-vv",
    ]

    if args.timeout:
        pytest_command += [
            "--timeout",
            args.timeout,
            "--timeout_method",
            "thread",
        ]

    if args.m != "all":
        pytest_command += ["-m", args.m]

    if args.model_name:
        pytest_command += ["--model-name", args.model_name]

    # pytest --junit-xml=test-results.xml --cov=azure.ai.ml --cov-report=html --cov-report=xml -ra ./tests/*/unittests/
    run_command(pytest_command)
