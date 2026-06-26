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

    # filename without extension + ::section: test_include::a should resolve to test_include.yaml, section a
    tests_dir = os.path.join(os.path.dirname(__file__))
    test_include_base = os.path.join(tests_dir, "test_include")
    conf, _ = load_conf(f"_include: {test_include_base}::a\n")
    assert conf.b == 1


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


def test_include_suffix_inplace_insertion(tmp_path):
    """_include_SUFFIX inserts included keys at the directive's position."""
    included_file = tmp_path / "middle.yaml"
    included_file.write_text("mid_key1:\n  val: 10\nmid_key2:\n  val: 20\n")

    parent_file = tmp_path / "parent_include.yaml"
    parent_file.write_text(
        f"step_a:\n  command: prep\n_include_middle: {included_file}\nstep_z:\n  command: finalize\n"
    )

    conf, _ = configuratt.load(str(parent_file), use_sources=[], verbose=False, use_cache=False)

    assert "step_a" in conf
    assert "mid_key1" in conf
    assert "mid_key2" in conf
    assert "step_z" in conf
    assert conf.step_a.command == "prep"
    assert conf.mid_key1.val == 10
    assert conf.mid_key2.val == 20
    assert conf.step_z.command == "finalize"
    assert "_include_middle" not in conf

    key_order = list(conf.keys())
    assert key_order.index("step_a") < key_order.index("mid_key1") < key_order.index("step_z")


def test_use_suffix_inplace_insertion(tmp_path):
    """_use_SUFFIX inserts referenced section's keys at the directive's position."""
    use_file = tmp_path / "use_inplace.yaml"
    use_file.write_text(
        "lib:\n  common:\n    val: 99\n\nsteps:\n  step_a:\n    x: 1\n  _use_common: lib.common\n  step_z:\n    x: 2\n"
    )

    conf, _ = configuratt.load(str(use_file), use_sources=[], verbose=False, use_cache=False)

    assert "lib" in conf
    steps = conf.steps
    assert "step_a" in steps
    assert "val" in steps
    assert "step_z" in steps
    assert steps.step_a.x == 1
    assert steps.val == 99
    assert steps.step_z.x == 2
    assert "_use_common" not in steps

    key_order = list(steps.keys())
    assert key_order.index("step_a") < key_order.index("val") < key_order.index("step_z")


def test_include_after_content_raises_error(tmp_path):
    """Bare _include after content keys raises ConfigurattError."""
    dummy_included = tmp_path / "dummy.yaml"
    dummy_included.write_text("x: 1\n")

    bad_include_file = tmp_path / "bad_include_top.yaml"
    bad_include_file.write_text(f"step_a:\n  command: prep\n_include: {dummy_included}\n")

    with pytest.raises(ConfigurattError, match="_include"):
        configuratt.load(str(bad_include_file), use_sources=[], verbose=False, use_cache=False)


def test_use_after_content_raises_error(tmp_path):
    """Bare _use after content keys raises ConfigurattError."""
    lib = tmp_path / "lib.yaml"
    lib.write_text("base:\n  x: 1\n")
    lib_conf = OmegaConf.load(str(lib))

    bad_use_file = tmp_path / "bad_use_top.yaml"
    bad_use_file.write_text("step_a:\n  command: prep\n_use: base\n")

    with pytest.raises(ConfigurattError, match="_use"):
        configuratt.load(str(bad_use_file), use_sources=[lib_conf], verbose=False, use_cache=False)


def test_orphaned_scrub_raises_error(tmp_path):
    """_scrub_<suffix> with no matching _include_<suffix> or _use_<suffix> raises ConfigurattError."""
    # orphaned _scrub_foo — no _include_foo or _use_foo
    bad_file = tmp_path / "orphan_scrub.yaml"
    bad_file.write_text("a: 1\n_scrub_foo: some_key\nb: 2\n")

    with pytest.raises(ConfigurattError, match="_scrub_foo"):
        configuratt.load(str(bad_file), use_sources=[], verbose=False, use_cache=False)


def test_orphaned_bare_scrub_raises_error(tmp_path):
    """Bare _scrub with no matching _include or _use raises ConfigurattError."""
    bad_file = tmp_path / "orphan_bare_scrub.yaml"
    bad_file.write_text("a: 1\n_scrub: some_key\nb: 2\n")

    with pytest.raises(ConfigurattError, match="_scrub"):
        configuratt.load(str(bad_file), use_sources=[], verbose=False, use_cache=False)


def test_include_post_placement_error(tmp_path):
    """_include_post before last content key raises ConfigurattError."""
    dummy_included = tmp_path / "dummy.yaml"
    dummy_included.write_text("x: 1\n")

    bad_post_file = tmp_path / "bad_include_post.yaml"
    bad_post_file.write_text(f"_include_post: {dummy_included}\nstep_a:\n  command: prep\n")

    with pytest.raises(ConfigurattError, match="_include_post"):
        configuratt.load(str(bad_post_file), use_sources=[], verbose=False, use_cache=False)


def test_use_post_placement_error(tmp_path):
    """_use_post before last content key raises ConfigurattError."""
    use_post_src = tmp_path / "use_post_src.yaml"
    use_post_src.write_text("lib:\n  key: 1\n")
    use_post_bad_file = tmp_path / "use_post_bad.yaml"
    use_post_bad_file.write_text("_use_post: lib\nstep_a:\n  x: 1\n")

    src_conf = OmegaConf.load(str(use_post_src))
    with pytest.raises(ConfigurattError, match="_use_post"):
        configuratt.load(str(use_post_bad_file), use_sources=[src_conf], verbose=False, use_cache=False)


def test_include_suffix_scrub(tmp_path):
    """_scrub_SUFFIX removes specified keys from the corresponding _include_SUFFIX result."""
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


def test_include_suffix_recursive(tmp_path):
    """Content brought in via _include_SUFFIX is itself fully resolved."""
    grandchild_file = tmp_path / "grandchild.yaml"
    grandchild_file.write_text("deep_key: 42\n")

    middle_file = tmp_path / "middle_recursive.yaml"
    middle_file.write_text(f"_include: {grandchild_file}\nmid_key: hello\n")

    parent_recursive = tmp_path / "parent_recursive.yaml"
    parent_recursive.write_text(f"before_key: 1\n_include_mid: {middle_file}\nafter_key: 2\n")

    conf, _ = configuratt.load(str(parent_recursive), use_sources=[], verbose=False, use_cache=False)

    assert "before_key" in conf
    assert "mid_key" in conf
    assert "deep_key" in conf
    assert "after_key" in conf
    assert conf.deep_key == 42
    assert "_include_mid" not in conf
    assert "_include" not in conf


def test_include_suffix_after_post_raises_error(tmp_path):
    """_include_SUFFIX appearing after _include_post raises ConfigurattError."""
    dummy_included = tmp_path / "dummy.yaml"
    dummy_included.write_text("x: 1\n")

    post_then_mid_file = tmp_path / "post_then_mid.yaml"
    post_then_mid_file.write_text(f"content_key: 1\n_include_post: {dummy_included}\n_include_mid: {dummy_included}\n")

    with pytest.raises(ConfigurattError, match="_include_post"):
        configuratt.load(str(post_then_mid_file), use_sources=[], verbose=False, use_cache=False)


def test_use_suffix_recursive(tmp_path):
    """Content brought in via _use_SUFFIX is itself fully resolved."""
    lib_recursive = tmp_path / "lib_recursive.yaml"
    lib_recursive.write_text("base:\n  deep_val: 99\nstep:\n  _use: base\n  x: 1\n")

    lib_conf = OmegaConf.load(str(lib_recursive))

    use_recursive_parent = tmp_path / "parent_use_recursive.yaml"
    use_recursive_parent.write_text("before: 1\n_use_mid: step\nafter: 2\n")

    conf, _ = configuratt.load(str(use_recursive_parent), use_sources=[lib_conf], verbose=False, use_cache=False)

    assert conf.before == 1
    assert conf.x == 1
    assert conf.deep_val == 99
    assert conf.after == 2
    assert "_use_mid" not in conf
    assert "_use" not in conf


def test_include_suffix_with_include_in_name(tmp_path):
    """Suffix containing 'include' doesn't corrupt _scrub key derivation."""
    included_file = tmp_path / "subinclude_source.yaml"
    included_file.write_text("keep_key:\n  val: 1\nremove_key:\n  val: 2\n")

    parent_file = tmp_path / "parent_subinclude.yaml"
    parent_file.write_text(
        f"step_a:\n  x: 1\n_include_subinclude: {included_file}\n_scrub_subinclude: remove_key\nstep_z:\n  x: 2\n"
    )

    conf, _ = configuratt.load(str(parent_file), use_sources=[], verbose=False, use_cache=False)

    assert "_include_subinclude" not in conf
    assert "_scrub_subinclude" not in conf
    assert "keep_key" in conf
    assert "remove_key" not in conf
    assert conf.step_a.x == 1
    assert conf.step_z.x == 2

    key_order = list(conf.keys())
    assert key_order.index("step_a") < key_order.index("keep_key") < key_order.index("step_z")


def test_use_suffix_with_use_in_name(tmp_path):
    """Suffix containing 'use' doesn't corrupt _scrub key derivation."""
    use_file = tmp_path / "use_reuse.yaml"
    use_file.write_text(
        "lib:\n  common:\n    keep_val: 99\n    drop_val: 0\n\n"
        "steps:\n  step_a:\n    x: 1\n  _use_reuse: lib.common\n  _scrub_reuse: drop_val\n  step_z:\n    x: 2\n"
    )

    conf, _ = configuratt.load(str(use_file), use_sources=[], verbose=False, use_cache=False)

    steps = conf.steps
    assert "_use_reuse" not in steps
    assert "_scrub_reuse" not in steps
    assert "keep_val" in steps
    assert "drop_val" not in steps
    assert steps.step_a.x == 1
    assert steps.step_z.x == 2

    key_order = list(steps.keys())
    assert key_order.index("step_a") < key_order.index("keep_val") < key_order.index("step_z")


# ---------------------------------------------------------------------------
# Positional priority semantics
# ---------------------------------------------------------------------------
# All directives (_include, _include_SUFFIX, _include_post, _use, _use_SUFFIX,
# _use_post) follow the same rule: later in the mapping = higher priority.
# The tests below check collision resolution at each position.


def test_include_top_loses_to_content(tmp_path):
    """_include at the top: content keys in the parent win on conflict."""
    inc = tmp_path / "base.yaml"
    inc.write_text("shared: from_include\nunique_inc: 1\n")

    parent = tmp_path / "parent.yaml"
    parent.write_text(f"_include: {inc}\nshared: from_parent\nunique_parent: 2\n")

    conf, _ = configuratt.load(str(parent), use_sources=[], verbose=False, use_cache=False)

    assert conf.shared == "from_parent"  # parent wins
    assert conf.unique_inc == 1  # non-conflicting key from include survives
    assert conf.unique_parent == 2


def test_include_post_wins_over_content(tmp_path):
    """_include_post at the bottom: included content wins on conflict."""
    inc = tmp_path / "override.yaml"
    inc.write_text("shared: from_post\nunique_post: 9\n")

    parent = tmp_path / "parent.yaml"
    parent.write_text(f"shared: from_parent\nunique_parent: 1\n_include_post: {inc}\n")

    conf, _ = configuratt.load(str(parent), use_sources=[], verbose=False, use_cache=False)

    assert conf.shared == "from_post"  # _include_post wins
    assert conf.unique_parent == 1  # non-conflicting key from parent survives
    assert conf.unique_post == 9


def test_include_suffix_positional_priority(tmp_path):
    """_include_SUFFIX: wins over keys before it, loses to keys after it."""
    inc = tmp_path / "middle.yaml"
    inc.write_text("before_key: from_include\nafter_key: from_include\nunique_mid: 42\n")

    parent = tmp_path / "parent.yaml"
    # before_key appears before the directive → include wins
    # after_key appears after the directive → parent wins
    parent.write_text(f"before_key: from_parent\n_include_mid: {inc}\nafter_key: from_parent\n")

    conf, _ = configuratt.load(str(parent), use_sources=[], verbose=False, use_cache=False)

    assert conf.before_key == "from_include"  # include overrides earlier key
    assert conf.after_key == "from_parent"  # later key overrides include
    assert conf.unique_mid == 42


def test_use_top_loses_to_content(tmp_path):
    """_use at the top: content keys in the current section win on conflict."""
    lib = tmp_path / "lib.yaml"
    lib.write_text("base:\n  shared: from_base\n  unique_base: 1\n")
    lib_conf = OmegaConf.load(str(lib))

    parent = tmp_path / "parent.yaml"
    parent.write_text("_use: base\nshared: from_parent\nunique_parent: 2\n")

    conf, _ = configuratt.load(str(parent), use_sources=[lib_conf], verbose=False, use_cache=False)

    assert conf.shared == "from_parent"  # parent wins
    assert conf.unique_base == 1  # non-conflicting key from base survives
    assert conf.unique_parent == 2


def test_use_post_wins_over_content(tmp_path):
    """_use_post at the bottom: referenced section wins on conflict."""
    lib = tmp_path / "lib.yaml"
    lib.write_text("override:\n  shared: from_post\n  unique_post: 9\n")
    lib_conf = OmegaConf.load(str(lib))

    parent = tmp_path / "parent.yaml"
    parent.write_text("shared: from_parent\nunique_parent: 1\n_use_post: override\n")

    conf, _ = configuratt.load(str(parent), use_sources=[lib_conf], verbose=False, use_cache=False)

    assert conf.shared == "from_post"  # _use_post wins
    assert conf.unique_parent == 1
    assert conf.unique_post == 9


def test_use_suffix_positional_priority(tmp_path):
    """_use_SUFFIX: wins over keys before it, loses to keys after it."""
    lib = tmp_path / "lib.yaml"
    lib.write_text("section:\n  before_key: from_use\n  after_key: from_use\n  unique_mid: 99\n")
    lib_conf = OmegaConf.load(str(lib))

    parent = tmp_path / "parent.yaml"
    parent.write_text("before_key: from_parent\n_use_mid: section\nafter_key: from_parent\n")

    conf, _ = configuratt.load(str(parent), use_sources=[lib_conf], verbose=False, use_cache=False)

    assert conf.before_key == "from_use"  # use overrides earlier key
    assert conf.after_key == "from_parent"  # later key overrides use
    assert conf.unique_mid == 99
