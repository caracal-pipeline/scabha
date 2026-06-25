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


def test_relative_use(tmp_path):
    """Test relative _use references using leading-dot notation."""

    # --- 1. .sibling: one leading dot resolves to a sibling in the same parent ---
    sibling_yaml = tmp_path / "test_relative_sibling.yaml"
    sibling_yaml.write_text(
        "steps:\n  step1:\n    cab: wsclean\n    size: 4096\n  step2:\n    _use: .step1\n    size: 2048\n"
    )
    conf, _ = configuratt.load(str(sibling_yaml), use_sources=[], verbose=False, use_cache=False)
    assert conf.steps.step2.cab == "wsclean", "step2 should inherit cab from step1"
    assert conf.steps.step2.size == 2048, "step2.size should override the inherited value"

    # --- 2. ..ancestor: two leading dots goes up two levels ---
    ancestor_yaml = tmp_path / "test_relative_ancestor.yaml"
    ancestor_yaml.write_text("base:\n  size: 1024\nsteps:\n  step1:\n    _use: ..base\n")
    conf, _ = configuratt.load(str(ancestor_yaml), use_sources=[], verbose=False, use_cache=False)
    assert conf.steps.step1.size == 1024, "step1 should inherit size from base via ..base"

    # --- 3. Absolute reference (no dots) still works unchanged ---
    absolute_yaml = tmp_path / "test_absolute_use.yaml"
    absolute_yaml.write_text("defaults:\n  niter: 100\nclean:\n  _use: defaults\n  threshold: 1e-4\n")
    conf, _ = configuratt.load(str(absolute_yaml), use_sources=[], verbose=False, use_cache=False)
    assert conf.clean.niter == 100, "absolute _use should still work"
    assert conf.clean.threshold == 1e-4

    # --- 4. Too many dots → raises ConfigurattError ---
    too_many_dots_yaml = tmp_path / "test_too_many_dots.yaml"
    too_many_dots_yaml.write_text(
        "steps:\n"
        "  step1:\n"
        "    cab: wsclean\n"
        "  step2:\n"
        "    _use: ...toohigh\n"  # steps.step2 is 2 levels deep; 3 dots goes above root
    )
    try:
        configuratt.load(str(too_many_dots_yaml), use_sources=[], verbose=False, use_cache=False)
        raise RuntimeError("ConfigurattError was expected for too-many-dots reference")
    except ConfigurattError as exc:
        print(f"Exception as expected (too many dots): {exc}")

    # --- 5. Relative _use at top level (location is None) → raises ConfigurattError ---
    toplevel_yaml = tmp_path / "test_toplevel_relative.yaml"
    toplevel_yaml.write_text(
        "base:\n  size: 42\n_use: .base\n"  # _use at the very top level, so location is None/empty
    )
    try:
        configuratt.load(str(toplevel_yaml), use_sources=[], verbose=False, use_cache=False)
        raise RuntimeError("ConfigurattError was expected for top-level relative _use")
    except ConfigurattError as exc:
        print(f"Exception as expected (top-level relative): {exc}")

    # --- 6. dots with no target name (e.g. _use: .) should raise ---
    no_target_yaml = tmp_path / "test_no_target.yaml"
    no_target_yaml.write_text("steps:\n  step1:\n    cab: wsclean\n  step2:\n    _use: .\n")
    with pytest.raises(ConfigurattError, match="no target name"):
        configuratt.load(str(no_target_yaml), use_sources=[], verbose=False, use_cache=False)

    # --- 7. relative _use inside a list element should raise (location contains '[') ---
    list_yaml = tmp_path / "test_list_use.yaml"
    list_yaml.write_text("lib:\n  base:\n    val: 42\nitems:\n  - _use: .lib\n")
    with pytest.raises(ConfigurattError, match="not valid inside a list"):
        configuratt.load(str(list_yaml), use_sources=[], verbose=False, use_cache=False)


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
