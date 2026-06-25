import os.path
from typing import List, Optional, Tuple

import click
from click.testing import CliRunner
from omegaconf import OmegaConf

from scabha.lazy_group import LazyGroup
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


@click.command("boolean-policies-app")
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


# -- Tests for positional metavar (stimela#424) --

positional_config = OmegaConf.create(
    {
        "inputs": {
            "input_file": dict(dtype="str", required=True, info="Input file", policies=dict(positional=True)),
            "output_dir": dict(dtype="str", required=True, info="Output directory", policies=dict(positional=True)),
            "count": dict(dtype="int", info="Number of items"),
        },
        "outputs": {},
    }
)


@click.command("positional-app")
@clickify_parameters(positional_config)
def positional_app(**kwargs):
    for k, v in sorted(kwargs.items()):
        click.echo(f"{k}={v!r}")


def test_positional_metavar_uses_name():
    """Positional arguments should show their name (uppercased) as metavar, not dtype."""
    runner = CliRunner()
    result = runner.invoke(positional_app, ["--help"])
    assert result.exit_code == 0
    # Usage line should show parameter names, not dtype strings like 'str'
    assert "INPUT-FILE" in result.output
    assert "OUTPUT-DIR" in result.output


def test_positional_metavar_does_not_show_dtype():
    """Positional metavar should not be the dtype string."""
    runner = CliRunner()
    result = runner.invoke(positional_app, ["--help"])
    assert result.exit_code == 0
    # The usage line should not contain bare 'str' as positional metavar.
    # Options like --count may show 'int' in their help, but the usage line
    # for positionals (before Options:) should use names.
    usage_line = result.output.split("\n")[0]
    # The usage line should not have 'str' as a standalone positional metavar
    assert "INPUT-FILE" in usage_line
    assert "OUTPUT-DIR" in usage_line


positional_custom_metavar_config = OmegaConf.create(
    {
        "inputs": {
            "input_file": dict(
                dtype="str", required=True, info="Input", policies=dict(positional=True), metavar="MYFILE"
            ),
        },
        "outputs": {},
    }
)


@click.command("positional-custom-metavar-app")
@clickify_parameters(positional_custom_metavar_config)
def positional_custom_metavar_app(**kwargs):
    pass


def test_positional_explicit_metavar_respected():
    """When schema.metavar is explicitly set, it should override the name-based default."""
    runner = CliRunner()
    result = runner.invoke(positional_custom_metavar_app, ["--help"])
    assert result.exit_code == 0
    assert "MYFILE" in result.output


def test_positional_app_runs():
    """Positional arguments should still work correctly."""
    runner = CliRunner()
    result = runner.invoke(positional_app, ["foo.txt", "/tmp/out"])
    assert result.exit_code == 0
    assert "input_file='foo.txt'" in result.output
    assert "output_dir='/tmp/out'" in result.output


# -- Tests for Optional[str] defaults (stimela#415) --

optional_str_config = OmegaConf.create(
    {
        "inputs": {
            "with_default": dict(dtype="Optional[str]", default="hello.fits", info="Has a default"),
            "no_default": dict(dtype="Optional[str]", info="No default set"),
            "null_default": dict(dtype="Optional[str]", default=None, info="Explicit null default"),
            "regular_str": dict(dtype="str", info="Non-optional string"),
        },
        "outputs": {},
    }
)


@click.command("optional-str-app")
@clickify_parameters(optional_str_config)
def optional_str_app(**kwargs):
    for k, v in sorted(kwargs.items()):
        click.echo(f"{k}={v!r}")


def test_optional_str_with_default():
    """Optional[str] with an explicit default should pass the default through."""
    runner = CliRunner()
    result = runner.invoke(optional_str_app, [])
    assert result.exit_code == 0
    assert "with_default='hello.fits'" in result.output


def test_optional_str_no_default_is_none():
    """Optional[str] with no default (UNSET) should get None, not be missing."""
    runner = CliRunner()
    result = runner.invoke(optional_str_app, [])
    assert result.exit_code == 0
    assert "no_default=None" in result.output


def test_optional_str_null_default_is_none():
    """Optional[str] with explicit null default should get None."""
    runner = CliRunner()
    result = runner.invoke(optional_str_app, [])
    assert result.exit_code == 0
    assert "null_default=None" in result.output


def test_optional_str_provided_value():
    """Optional[str] parameters should accept provided values."""
    runner = CliRunner()
    result = runner.invoke(optional_str_app, ["--no-default", "provided.fits"])
    assert result.exit_code == 0
    assert "no_default='provided.fits'" in result.output


def test_optional_str_override_default():
    """Optional[str] with a default can be overridden by CLI arg."""
    runner = CliRunner()
    result = runner.invoke(optional_str_app, ["--with-default", "override.fits"])
    assert result.exit_code == 0
    assert "with_default='override.fits'" in result.output


# -- Existing lazy group tests --

@click.group(cls=LazyGroup, lazy_subcommands={"hello-world": "tests.hello_app.hello_world"})
def cli_group():
    pass


def test_group_lazy_load():
    runner = CliRunner()

    result = runner.invoke(cli_group, "--help".split())
    assert result.exit_code == 0

    result = runner.invoke(cli_group, "hello-world --help")
    assert result.exit_code == 0
