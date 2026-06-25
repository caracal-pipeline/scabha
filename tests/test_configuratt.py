import os.path
import sys
from typing import Any, Dict

import pytest
from omegaconf import OmegaConf

from scabha import configuratt
from scabha.configuratt import ConfigurattError


# Change into directory where test_recipy.py lives
# As suggested by https://stackoverflow.com/questions/62044541/change-pytest-working-directory-to-test-case-directory
@pytest.fixture(autouse=True)
def change_test_dir(request, monkeypatch):
    monkeypatch.chdir(request.fspath.dirname)


def test_includes():
    path = "testconf.yaml"
    conf, deps = configuratt.load(path, use_sources=[], verbose=True, use_cache=False)
    assert conf.x.y2.z1 == 1
    assert conf.relative.x.y == "a"

    assert conf.basename == "testconf.yaml"

    missing = configuratt.check_requirements(conf, [], strict=False)
    assert len(missing) == 2  # 2 failed reqs
    assert "yy" not in conf.requirements2.x  # this one was contingent, so section was deleted
    assert missing[0][2] is None  # this one was contingent, so no error
    assert type(missing[1][2]) is ConfigurattError  # this one was required, so yes error

    try:
        conf, deps = configuratt.load(path, use_sources=[], verbose=True, use_cache=False)
        missing = configuratt.check_requirements(conf, [], strict=True)
        raise RuntimeError("Error was expected here!")
    except configuratt.ConfigurattError as exc:
        print(f"Exception as expected: {exc}")

    try:
        conf, deps = configuratt.load("test_recursive_include.yml", use_sources=[], verbose=True, use_cache=False)
        raise RuntimeError("Error was expected here!")
    except configuratt.ConfigurattError as exc:
        print(f"Exception as expected: {exc}")

    nested = ["test_nest_a.yml", "test_nest_b.yml", "test_nest_c.yml"]
    nested = [os.path.join(os.path.dirname(path), name) for name in nested]

    conf1, deps1 = configuratt.load_nested(
        nested, typeinfo=Dict[str, Any], nameattr="_name", verbose=True, use_cache=False
    )
    conf["nested"] = conf1
    OmegaConf.save(conf, sys.stderr)

    deps.update(deps1)

    print(f"Dependencies are: {deps.get_description()}")


def test_colon_section_syntax(tmp_path):
    """Test filename::section and filename::nested.section syntax for _include."""
    source = tmp_path / "source.yaml"
    source.write_text(
        "cabs:\n  wsclean:\n    command: wsclean\n  casa:\n    command: casa\nmeta:\n  version: '1.0'\nscalar: hello\n"
    )

    counter = [0]

    def load_conf(content):
        p = tmp_path / f"p{counter[0]}.yaml"
        counter[0] += 1
        p.write_text(content)
        return configuratt.load(str(p), use_sources=[], verbose=False, use_cache=False)

    # filename::section selects a top-level subsection
    conf, _ = load_conf(f"_include: {source}::cabs\n")
    assert "wsclean" in conf and "casa" in conf and "meta" not in conf

    # filename::nested.section selects via dotted path
    conf, _ = load_conf(f"_include: {source}::cabs.wsclean\n")
    assert conf.command == "wsclean" and "casa" not in conf

    # missing section with [optional] is silently skipped; other keys survive
    conf, _ = load_conf(f"_include: {source}::no_such [optional]\nfallback: 1\n")
    assert conf.fallback == 1 and "cabs" not in conf

    # missing section without [optional] raises ConfigurattError
    with pytest.raises(ConfigurattError, match="section.*not found"):
        load_conf(f"_include: {source}::no_such\n")

    # section resolving to a scalar (not a mapping) raises ConfigurattError
    with pytest.raises(ConfigurattError, match="not a mapping"):
        load_conf(f"_include: {source}::scalar\n")


def test_colon_module_syntax(tmp_path):
    """Test module::filename.yml and module::filename.yml::section syntax for _include."""
    counter = [0]

    def load_conf(content):
        p = tmp_path / f"p{counter[0]}.yaml"
        counter[0] += 1
        p.write_text(content)
        return configuratt.load(str(p), use_sources=[], verbose=False, use_cache=False)

    # module::filename loads from the module's package directory
    conf, _ = load_conf("_include: tests::test_include.yaml\n")
    assert "x" in conf

    # module::filename without extension uses implicit extension resolution (.yaml/.yml)
    conf, _ = load_conf("_include: tests::test_include\n")
    assert "x" in conf

    # module::filename::section loads a subsection from a module file
    conf, _ = load_conf("_include: tests::test_include.yaml::a\n")
    assert conf.b == 1

    # optional unknown module is silently skipped; other keys survive
    conf, _ = load_conf("_include: no_such_module_xyz::file.yaml [optional]\nfallback: 1\n")
    assert conf.fallback == 1

    # required unknown module raises ConfigurattError
    with pytest.raises(ConfigurattError, match="can't find module"):
        load_conf("_include: no_such_module_xyz::file.yaml\n")


def test_tilde_include(tmp_path):
    from pathlib import Path

    home = Path.home()
    include_file = home / ".scabha_pytest_tilde_test.yaml"
    include_file.write_text("tilde_included:\n  value: 42\n")
    try:
        parent = tmp_path / "tilde_parent.yaml"
        parent.write_text("_include: ~/.scabha_pytest_tilde_test.yaml\n")
        conf, _ = configuratt.load(str(parent), use_sources=[], verbose=False, use_cache=False)
        assert conf.tilde_included.value == 42
    finally:
        include_file.unlink(missing_ok=True)
