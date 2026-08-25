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
    usage_line = result.output.split("\n")[0]
    # Usage line should show parameter names, not dtype strings like 'str'
    assert "INPUT-FILE" in usage_line
    assert "OUTPUT-DIR" in usage_line
    # dtype should not appear as a standalone metavar in the usage line
    usage_tokens = usage_line.split()
    assert "str" not in usage_tokens, f"dtype 'str' should not appear as metavar in usage line: {usage_line}"


def test_positional_metavar_does_not_show_dtype():
    """Positional metavar should not be the dtype string."""
    runner = CliRunner()
    result = runner.invoke(positional_app, ["--help"])
    assert result.exit_code == 0
    usage_line = result.output.split("\n")[0]
    assert "INPUT-FILE" in usage_line
    assert "OUTPUT-DIR" in usage_line
    usage_tokens = usage_line.split()
    assert "str" not in usage_tokens, f"dtype 'str' should not appear as metavar in usage line: {usage_line}"


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


# -- Tests for List[str] defaults surfacing uncorrupted with no CLI override
# (surfaced by ratt-ru/breifast#278's filter-by-metadata option: a schema
# default of ['ProposalId'] was reaching the command's callback as the
# repr-quoted string "'ProposalId'" instead of the plain "ProposalId") --

list_default_config = OmegaConf.create(
    {
        "inputs": {
            "tags": dict(dtype="List[str]", default=["ProposalId"], info="single-element default"),
            "many": dict(dtype="List[str]", default=["a", "b", "c"], info="multi-element default"),
            "bracketed": dict(
                dtype="List[str]", default=["x", "y"], policies=dict(repeat="[]"),
                info="bracket-syntax repeat policy",
            ),
            "colon-sep": dict(
                dtype="List[str]", default=["p", "q"], policies=dict(repeat=":"),
                info="a different separator, defined right after the default (',') ones -- "
                     "regression case for the loop-variable late-binding bug",
            ),
            "has-separator-in-value": dict(
                dtype="List[str]", default=["a,b", "c"],
                info="an element containing the configured separator itself -- must not be "
                     "split back apart when the default is what's rendered, not real input",
            ),
            "tup-bracketed": dict(
                dtype="Tuple[int, str]", default=[1, "x"], policies=dict(repeat="[]"),
                info="tuple, bracket-syntax repeat policy",
            ),
            "tup-sep": dict(
                dtype="Tuple[int, str]", default=[2, "y"],
                info="tuple, default ',' separator repeat policy",
            ),
        },
        "outputs": {},
    }
)


@click.command("list-default-app")
@clickify_parameters(list_default_config)
def list_default_app(**kwargs):
    for k, v in sorted(kwargs.items()):
        click.echo(f"{k}={v!r}")


def test_list_default_single_element_not_corrupted():
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "tags=['ProposalId']" in result.output


def test_list_default_multi_element_not_corrupted():
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "many=['a', 'b', 'c']" in result.output


def test_list_default_bracket_repeat_policy_not_corrupted():
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "bracketed=['x', 'y']" in result.output


def test_list_default_still_overridable_from_cli():
    runner = CliRunner()
    result = runner.invoke(list_default_app, ["--tags", "Foo,Bar"])
    assert result.exit_code == 0, result.output
    assert "tags=['Foo', 'Bar']" in result.output


def test_list_default_element_containing_the_separator_is_not_split():
    # The default is handed back untouched rather than round-tripped
    # through str-join-then-split, so an element that happens to contain
    # the configured separator survives intact -- "a,b" stays one element,
    # not two.
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "has_separator_in_value=['a,b', 'c']" in result.output


def test_two_list_options_with_different_separators_each_keep_their_own_default():
    # Regression for the loop-variable late-binding bug: 'tags'/'many' use
    # the default ',' policy, 'colon-sep' is defined right after them with
    # ':' -- each option's callback must use its own separator, not
    # whichever one the parameter-schema loop had last set when the
    # callback closures were created.
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "colon_sep=['p', 'q']" in result.output
    # And each is still independently overridable with its own separator.
    result = runner.invoke(list_default_app, ["--colon-sep", "m:n", "--tags", "Foo,Bar"])
    assert result.exit_code == 0, result.output
    assert "colon_sep=['m', 'n']" in result.output
    assert "tags=['Foo', 'Bar']" in result.output


def test_tuple_default_bracket_repeat_policy_not_corrupted():
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "tup_bracketed=(1, 'x')" in result.output


def test_tuple_default_separator_repeat_policy_not_corrupted():
    runner = CliRunner()
    result = runner.invoke(list_default_app, [])
    assert result.exit_code == 0, result.output
    assert "tup_sep=(2, 'y')" in result.output


def test_tuple_default_still_overridable_from_cli():
    runner = CliRunner()
    result = runner.invoke(list_default_app, ["--tup-sep", "9,z"])
    assert result.exit_code == 0, result.output
    assert "tup_sep=(9, 'z')" in result.output


# -- Existing lazy group tests --


@click.group(cls=LazyGroup, lazy_subcommands={"hello-world": "hello_app.hello_world"})
def cli_group():
    pass


def test_group_lazy_load():
    runner = CliRunner()

    result = runner.invoke(cli_group, "--help".split())
    assert result.exit_code == 0

    result = runner.invoke(cli_group, "hello-world --help")
    assert result.exit_code == 0
