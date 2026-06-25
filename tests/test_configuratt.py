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

    # -------------------------------------------------------------------------
    # 7. Recursive resolution: content brought in via _include_SUFFIX must itself
    #    be fully resolved (nested _include directives inside the included file
    #    must be processed, not left as raw keys in the output).
    # -------------------------------------------------------------------------
    grandchild_file = tmp_path / "grandchild.yaml"
    grandchild_file.write_text("deep_key: 42\n")

    middle_file = tmp_path / "middle_recursive.yaml"
    middle_file.write_text(f"_include: {grandchild_file}\nmid_key: hello\n")

    parent_recursive = tmp_path / "parent_recursive.yaml"
    parent_recursive.write_text(f"before_key: 1\n_include_mid: {middle_file}\nafter_key: 2\n")

    conf, _ = configuratt.load(str(parent_recursive), use_sources=[], verbose=False, use_cache=False)

    # Keys from all three levels must be present
    assert "before_key" in conf
    assert "mid_key" in conf
    assert "deep_key" in conf
    assert "after_key" in conf

    # Grandchild value must be correct (recursively resolved)
    assert conf.deep_key == 42

    # No directive keys must survive
    assert "_include_mid" not in conf
    assert "_include" not in conf


def test_suffix_containing_keyword(tmp_path):
    """Tests that suffixes containing 'include' or 'use' in their name don't corrupt scrub-key derivation.

    Covers the bug where `keyword.replace("include", "scrub")` would transform
    `_include_subinclude` → `_scrub_subscrub` instead of `_scrub_subinclude`, and
    `_use_reuse` → `_scrub_rescrub` instead of `_scrub_reuse`.
    """
    # -------------------------------------------------------------------------
    # 1. _include_subinclude: suffix contains "include"
    # -------------------------------------------------------------------------
    included_file = tmp_path / "subinclude_source.yaml"
    included_file.write_text("keep_key:\n  val: 1\nremove_key:\n  val: 2\n")

    parent_file = tmp_path / "parent_subinclude.yaml"
    parent_file.write_text(
        f"step_a:\n  x: 1\n_include_subinclude: {included_file}\n_scrub_subinclude: remove_key\nstep_z:\n  x: 2\n"
    )

    conf, _ = configuratt.load(str(parent_file), use_sources=[], verbose=False, use_cache=False)

    # Directive key must not survive
    assert "_include_subinclude" not in conf
    assert "_scrub_subinclude" not in conf

    # Included content is present in-place (minus scrubbed key)
    assert "keep_key" in conf
    assert "remove_key" not in conf

    # Surrounding keys survive
    assert conf.step_a.x == 1
    assert conf.step_z.x == 2

    # Insertion order: step_a, keep_key, step_z
    key_order = list(conf.keys())
    assert key_order.index("step_a") < key_order.index("keep_key") < key_order.index("step_z")

    # -------------------------------------------------------------------------
    # 2. _use_reuse: suffix contains "use"
    # -------------------------------------------------------------------------
    use_file = tmp_path / "use_reuse.yaml"
    use_file.write_text(
        "lib:\n  common:\n    keep_val: 99\n    drop_val: 0\n\n"
        "steps:\n  step_a:\n    x: 1\n  _use_reuse: lib.common\n  _scrub_reuse: drop_val\n  step_z:\n    x: 2\n"
    )

    conf, _ = configuratt.load(str(use_file), use_sources=[], verbose=False, use_cache=False)

    steps = conf.steps

    # Directive keys must not survive
    assert "_use_reuse" not in steps
    assert "_scrub_reuse" not in steps

    # Used content is present in-place (minus scrubbed key)
    assert "keep_val" in steps
    assert "drop_val" not in steps

    # Surrounding keys survive
    assert steps.step_a.x == 1
    assert steps.step_z.x == 2

    # Insertion order: step_a, keep_val, step_z
    key_order = list(steps.keys())
    assert key_order.index("step_a") < key_order.index("keep_val") < key_order.index("step_z")
