import os.path
from typing import List, Optional, Tuple

import click
from click.testing import CliRunner
from omegaconf import OmegaConf

from scabha.schema_utils import clickify_parameters

schema_file = os.path.join(os.path.dirname(__file__), "test_clickify.yaml")


@click.command()
@clickify_parameters(schema_file)
def file_config_app(
    name: str,
    i: int,
    j: Optional[float] = 1,
    remainder: Optional[List[str]] = None,
    k: float = 2,
    tup: Optional[Tuple[int, str]] = None,
    files1: Optional[List[str]] = None,
    files2: Optional[List[str]] = None,
    files3: Optional[List[str]] = None,
    output: str = None,
):
    print(f"name:{name} i:{i} j:{j} k:{k} tup:{tup}")
    print(f"remainder: {remainder}")
    print(f"files1: {files1}")
    print(f"files2: {files2}")
    print(f"files3: {files3}")
    print(f"output: {output}")


def test_file_config():
    runner = CliRunner()
    result = runner.invoke(file_config_app, "--j 2 Foo 1".split())
    assert result.exit_code == 0


config = OmegaConf.create(
    {
        "inputs": {
            "flag": dict(info="foo Bar", dtype="bool", policies=dict(is_flag=True)),
            "explicit-flag": dict(info="foo Bar", dtype="bool", policies=dict(explicit_flag=True)),
            "yes-no-flag": dict(info="foo Bar", dtype="bool"),
        },
        "outputs": {},
    }
)


@click.command()
@clickify_parameters(config)
def boolean_policies_app(**kwargs):
    assert isinstance(kwargs["flag"], bool)


def test_boolean_policies_error_is_flag():
    runner = CliRunner()
    result = runner.invoke(boolean_policies_app, "--flag true".split())
    assert "unexpected extra argument" in result.output
    assert result.exit_code != 0

    result = runner.invoke(boolean_policies_app, ["--flag"])
    assert result.exit_code == 0


def test_boolean_policies_error_explicit_flag():
    runner = CliRunner()
    result = runner.invoke(boolean_policies_app, "--explicit-flag FooBar".split())
    assert "Invalid value" in result.output
    assert result.exit_code != 0

    result = runner.invoke(boolean_policies_app, "--explicit-flag false".split())
    assert result.exit_code == 0


def test_boolean_policies_explicit_yes_no():
    runner = CliRunner()
    result = runner.invoke(boolean_policies_app, "--yes-no-flag".split())
    assert result.exit_code == 0

    result = runner.invoke(boolean_policies_app, "--yes-no-flag true".split())
    assert "unexpected extra argument" in result.output
    assert result.exit_code != 0

    result = runner.invoke(boolean_policies_app, "--no-yes-no-flag".split())
    assert result.exit_code == 0
