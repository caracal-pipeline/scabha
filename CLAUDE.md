# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install (recommended with uv):**
```
uv sync --group dev
uv run pre-commit install
```

**Tests:**
```
uv run pytest tests                                      # all tests
uv run pytest tests/test_configuratt.py::test_includes  # single test
uv run pytest -v tests                                   # verbose
```

The active venv in this environment is `~/.venv/breifast`; invoke pytest as `~/.venv/breifast/bin/python -m pytest`.

**Lint / format:**
```
uv run ruff check
uv run ruff format
```

Line length is 120 (see `ruff.toml`). Pre-commit runs ruff automatically on commit.

## Architecture

Scabha is a parameter schema, validation, and CLI-generation library used primarily by radio-astronomy pipelines (Stimela). The central data flow is:

1. **YAML config loading** (`scabha.configuratt`) — loads configs with inheritance via `_include` / `_use` / `_scrub` directives, variable substitution, and optional/required dep checking. The main entry points are `configuratt.load()` and `configuratt.load_nested()`.

2. **Schema definition** (`scabha.cargo`) — `Parameter` and `ParameterPolicies` describe a single named parameter (dtype, default, choices, policies for CLI/validation behaviour). Collections of parameters form a `Cargo`.

3. **Validation** (`scabha.validate`) — `validate_parameters()` takes a dict of values + a dict of `Parameter` schemas and runs Pydantic v2 coercion, required checks, and `{}`-style substitutions.

4. **CLI generation** (`scabha.schema_utils`) — `schema_to_dataclass()` converts a parameter schema to a Python dataclass; `clickify_parameters()` decorates a Click command with options derived from the schema.

5. **Substitutions** (`scabha.substitutions`) — `SubstitutionNS` wraps OmegaConf nodes and resolves `{key}` / `{ns.key}` references lazily. `SubstitutionContext` manages a stack of namespaces.

6. **Special types** (`scabha.basetypes`) — `UNSET` sentinel, `Unresolved`, `Placeholder`, `URI`, `File`, `Directory`, `MS` (MeasurementSet). These integrate with typeguard for runtime checks.

### `scabha.configuratt` internals

`core.py:resolve_config_refs()` is the recursive workhorse. It handles:
- `_include` paths: module-qualified `(pkg)file`, current-dir `(.)file`, and plain paths with `~` expansion (`os.path.expanduser`) and multi-location search via `configuratt.common.PATH`.
- `_use` aliases, `_flatten`, `_scrub` / `_scrub_post`, `_include_post`.
- Recursion detection via `include_stack`.

`ConfigDependencies` (`deps.py`) records every loaded file (mtime, MD5, git info) for cache invalidation.

### Test fixtures

All YAML fixtures live in `tests/`. The autouse `change_test_dir` fixture in `test_configuratt.py` chdirs to `tests/` before each test so relative file paths in YAML work. Tests that need absolute or `tmp_path`-based files pass full paths to `configuratt.load()` directly (bypassing the cwd dependency).
