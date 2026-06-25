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


def test_arbitrary_placement(tmp_path):
    """Tests for _include_SUFFIX / _use_SUFFIX in-place insertion and placement enforcement."""

    # -------------------------------------------------------------------------
    # 1. _include_SUFFIX: in-place insertion
    # Write a file to be included, then a parent that includes it in the middle.
    # -------------------------------------------------------------------------
    included_file = tmp_path / "middle.yaml"
    included_file.write_text("mid_key1:\n  val: 10\nmid_key2:\n  val: 20\n")

    parent_file = tmp_path / "parent_include.yaml"
    parent_file.write_text(
        f"step_a:\n  command: prep\n_include_middle: {included_file}\nstep_z:\n  command: finalize\n"
    )

    conf, _ = configuratt.load(str(parent_file), use_sources=[], verbose=False, use_cache=False)

    # All keys must be present
    assert "step_a" in conf
    assert "mid_key1" in conf
    assert "mid_key2" in conf
    assert "step_z" in conf

    # Values must be correct
    assert conf.step_a.command == "prep"
    assert conf.mid_key1.val == 10
    assert conf.mid_key2.val == 20
    assert conf.step_z.command == "finalize"

    # No directive key should survive in the output
    assert "_include_middle" not in conf

    # Keys must appear in insertion order: step_a, then mid_key1, then step_z
    key_order = list(conf.keys())
    assert key_order.index("step_a") < key_order.index("mid_key1") < key_order.index("step_z")

    # -------------------------------------------------------------------------
    # 2. _use_SUFFIX: in-place insertion (self-referencing config)
    # The loaded config is prepended to use_sources=[] so it is the only source.
    # -------------------------------------------------------------------------
    use_file = tmp_path / "use_inplace.yaml"
    use_file.write_text(
        "lib:\n  common:\n    val: 99\n\nsteps:\n  step_a:\n    x: 1\n  _use_common: lib.common\n  step_z:\n    x: 2\n"
    )

    conf, _ = configuratt.load(str(use_file), use_sources=[], verbose=False, use_cache=False)

    # lib section is still present at top level
    assert "lib" in conf

    # steps section should have step_a, val (from lib.common), and step_z
    steps = conf.steps
    assert "step_a" in steps
    assert "val" in steps
    assert "step_z" in steps

    assert steps.step_a.x == 1
    assert steps.val == 99
    assert steps.step_z.x == 2

    # Directive key must not survive
    assert "_use_common" not in steps

    # Keys must appear in insertion order: step_a, then val, then step_z
    key_order = list(steps.keys())
    assert key_order.index("step_a") < key_order.index("val") < key_order.index("step_z")

    # -------------------------------------------------------------------------
    # 3. Placement error: _include after content keys raises ConfigurattError
    # -------------------------------------------------------------------------
    bad_include_file = tmp_path / "bad_include_top.yaml"
    # We need an included file that at least exists (content doesn't matter for this error)
    dummy_included = tmp_path / "dummy.yaml"
    dummy_included.write_text("x: 1\n")

    bad_include_file.write_text(f"step_a:\n  command: prep\n_include: {dummy_included}\n")

    with pytest.raises(ConfigurattError, match="_include"):
        configuratt.load(str(bad_include_file), use_sources=[], verbose=False, use_cache=False)

    # -------------------------------------------------------------------------
    # 4. Placement error: _include_post before last content key raises ConfigurattError
    # -------------------------------------------------------------------------
    bad_post_file = tmp_path / "bad_include_post.yaml"
    bad_post_file.write_text(f"_include_post: {dummy_included}\nstep_a:\n  command: prep\n")

    with pytest.raises(ConfigurattError, match="_include_post"):
        configuratt.load(str(bad_post_file), use_sources=[], verbose=False, use_cache=False)

    # -------------------------------------------------------------------------
    # 5. _use_post is still treated as post-only, not as arbitrary-suffix
    #    (i.e., _use_post is invalid when it has content after it — it must be
    #    at the bottom; content before it is fine)
    # -------------------------------------------------------------------------
    use_post_bad_file = tmp_path / "use_post_bad.yaml"
    use_post_src = tmp_path / "use_post_src.yaml"
    use_post_src.write_text("lib:\n  key: 1\n")
    # _use_post appearing before content (i.e., not at the bottom) should raise a placement error
    use_post_bad_file.write_text("_use_post: lib\nstep_a:\n  x: 1\n")

    # Load with the source config that contains lib
    src_conf = OmegaConf.load(str(use_post_src))
    with pytest.raises(ConfigurattError, match="_use_post"):
        configuratt.load(str(use_post_bad_file), use_sources=[src_conf], verbose=False, use_cache=False)

    # -------------------------------------------------------------------------
    # 6. _scrub_SUFFIX scrubs keys from the corresponding _include_SUFFIX result
    # -------------------------------------------------------------------------
    scrub_included = tmp_path / "scrub_source.yaml"
    scrub_included.write_text("keep_key:\n  val: 1\nremove_key:\n  val: 2\n")

    scrub_parent = tmp_path / "parent_scrub.yaml"
    scrub_parent.write_text(
        f"step_a:\n  x: 1\n_include_mid: {scrub_included}\n_scrub_mid: remove_key\nstep_z:\n  x: 2\n"
    )

    conf, _ = configuratt.load(str(scrub_parent), use_sources=[], verbose=False, use_cache=False)
    assert "keep_key" in conf
    assert "remove_key" not in conf
    assert "step_a" in conf and "step_z" in conf
