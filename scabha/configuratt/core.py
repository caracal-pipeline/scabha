import importlib
import os.path
import re
import uuid
from collections.abc import Sequence
from dataclasses import make_dataclass
from typing import Any, Callable, List, Optional, Union

from omegaconf.errors import OmegaConfBaseException
from omegaconf.omegaconf import DictConfig, ListConfig, OmegaConf
from yaml.error import YAMLError

from .cache import load_cache, save_cache
from .common import IMPLICIT_EXTENSIONS, PATH, ConfigurattError, pop_conf
from .deps import ConfigDependencies, FailRecord
from .helpers import _abs_use_name, _lookup_name, _scrub_subsections


def load(
    path: str,
    use_sources: Optional[List[DictConfig]] = [],
    name: Optional[str] = None,
    location: Optional[str] = None,
    includes: bool = True,
    selfrefs: bool = True,
    include_path: str = None,
    use_cache: bool = True,
    no_toplevel_cache=False,
    include_stack=[],
    verbose: bool = False,
):
    """Loads config file, using a previously loaded config to resolve _use references.

    Args:
        path (str): path to config file
        use_sources (Optional[List[DictConfig]]): list of existing configs to be used to resolve "_use" references,
                or None to disable
        name (Optional[str]): name of this config file, used for error messages
        location (Optional[str]): location where this config is being loaded (if not at root level)
        includes (bool, optional): If True (default), "_include" references will be processed
        selfrefs (bool, optional): If False, "_use" references will only be looked up in existing config.
            If True (default), they'll also be looked up within the loaded config.
        include_stack: list of paths which have been included. Used to catch recursive includes.
        include_path (str, optional):
            if set, path to each config file will be included in the section as element 'include_path'

    Returns:
        Tuple of (conf, dependencies)
            conf (DictConfig): config object
            dependencies (ConfigDependencies): filenames that were _included
    """
    use_toplevel_cache = use_cache and not no_toplevel_cache
    conf, dependencies = load_cache((path,), verbose=verbose) if use_toplevel_cache else (None, None)

    if conf is None:
        # create self:xxx resolver
        self_namespace = dict(path=path, dirname=os.path.dirname(path), basename=os.path.basename(path))

        def self_namespace_resolver(arg):
            if arg in self_namespace:
                return self_namespace[arg]
            raise KeyError(f"invalid '${{self:arg}}' substitution in {path}")

        OmegaConf.register_new_resolver("self", self_namespace_resolver)
        try:
            subconf = OmegaConf.load(path)
            # force resolution of interpolations at this point (otherwise they happen lazily)
            resolved = OmegaConf.to_container(subconf, resolve=True)
            subconf = OmegaConf.create(resolved)
        finally:
            OmegaConf.clear_resolver("self")

        name = name or os.path.basename(path)
        dependencies = ConfigDependencies()
        dependencies.add(path)
        # include ourself into sources, if _use is in effect, and we've enabled selfrefs
        if use_sources is not None and selfrefs:
            use_sources = [subconf] + list(use_sources)
        conf, deps = resolve_config_refs(
            subconf,
            pathname=path,
            location=location,
            name=name,
            includes=includes,
            use_cache=use_cache,
            use_sources=use_sources,
            include_path=include_path,
            include_stack=include_stack + [path],
        )
        # update overall dependencies
        dependencies.update(deps)

        # # check for missing requirements
        # dependencies.scan_requirements(conf, location, path)

        if use_cache:
            save_cache((path,), conf, dependencies, verbose=verbose)

    return conf, dependencies


def load_nested(
    filelist: List[str],
    structured: Optional[DictConfig] = None,
    typeinfo=None,
    use_sources: Optional[List[DictConfig]] = [],
    location: Optional[str] = None,
    nameattr: Union[Callable, str, None] = None,
    config_class: Optional[str] = None,
    include_path: Optional[str] = None,
    use_cache: bool = True,
    verbose: bool = False,
):
    """Builds nested configuration from a set of YAML files corresponding to sub-sections

    Parameters
    ----------
    conf : OmegaConf object
        root OmegaConf object to merge content into
    filelist : List[str]
        list of subsection config files to load
    schema : Optional[DictConfig]
        schema to be applied to each file, if any
    use_sources : Optional[List[DictConfig]]
        list of existing configs to be used to resolve "_use" references, or None to disable
    location : Optional[str]
        if set, contents of files are being loaded under 'location.subsection_name'. If not set, then 'subsection_name'
        is being loaded at root level. This is used for correctly formatting error messages and such.
    nameattr : Union[Callable, str, None]
        if None, subsection_name will be taken from the basename of the file. If set to a string such as 'name', will
        set subsection_name from that field in the subsection config. If callable, will be called with the subsection
        config object as a single argument, and must return the subsection name
    config_class : Optional[str]
        name of config dataclass to form (when using typeinfo), if None, then generated automatically
    include_path : Optional[str]
        if set, path to each config file will be included in the section as element 'include_path'

    Returns
    -------
        Tuple of (conf, dependencies)
            conf (DictConfig): config object
            dependencies (set): set of filenames that were _included

    Raises
    ------
    NameError
        If subsection name is not resolved
    """
    section_content, dependencies = load_cache(filelist, verbose=verbose) if use_cache else (None, None)

    if section_content is None:
        section_content = {}  # OmegaConf.create()
        dependencies = ConfigDependencies()

        for path in filelist:
            # load file
            subconf, deps = load(path, location=location, use_sources=use_sources, include_path=include_path)
            dependencies.update(deps)
            if include_path:
                subconf[include_path] = path

            # figure out section name
            if nameattr is None:
                name = os.path.splitext(os.path.basename(path))[0]
            elif callable(nameattr):
                name = nameattr(subconf)
            elif nameattr in subconf:
                name = subconf.get(nameattr)
            else:
                raise NameError(f"{path} does not contain a '{nameattr}' field")

            # apply schema
            if structured is not None:
                try:
                    subconf = OmegaConf.merge(structured, subconf)
                except (OmegaConfBaseException, YAMLError) as exc:
                    raise ConfigurattError(f"schema error in {path}: {exc}")

            section_content[name] = subconf

        if structured is None and typeinfo is not None:
            if config_class is None:
                config_class = "ConfigClass_" + uuid.uuid4().hex
            fields = [(name, typeinfo) for name in section_content.keys()]
            datacls = make_dataclass(config_class, fields)
            # datacls.__module__ == __name__  # for pickling
            structured = OmegaConf.structured(datacls)
            section_content = OmegaConf.merge(structured, section_content)

        if use_cache:
            save_cache(filelist, section_content, dependencies, verbose=verbose)

    return section_content, dependencies


def resolve_config_refs(
    conf,
    pathname: str,
    location: str,
    name: str,
    includes: bool,
    use_sources: Optional[List[DictConfig]],
    use_cache=True,
    include_path: Optional[str] = None,
    include_stack=[],
):
    """Resolves cross-references ("_use" and "_include" statements) in config object

    Parameters
    ----------
    conf : OmegaConf object
        input configuration object
    pathname : str
        full path to this config (directory component of that is used for _includes)
    location : str
        location of this configuration section, used for messages
    name : str
        name of this configuration file, used for messages
    includes : bool
        If True, "_include" references will be processed
    use_sources : optional list of OmegaConf objects
        one or more config object(s) in which to look up "_use" references. None to disable _use statements
    include_path (str, optional):
        if set, path to each config file will be included in the section as element 'include_path'
    include_stack (list, optional):
        stack of files from which this one was included. Used to catch recursion.

    Returns
    -------
    Tuple of (conf, dependencies)
    conf : OmegaConf object
        This may be a new object if a _use key was resolved, or it may be the existing object
    dependencies : ConfigDependencies
        Set of filenames that were _included

    Raises
    ------
    ConfigurattError
        If a _use or _include directive is malformed
    """
    errloc = f"config error at {location or 'top level'} in {name}"
    dependencies = ConfigDependencies()
    # self-referencing enabled if first source is ourselves
    selfrefs = use_sources and conf is use_sources[0]

    if isinstance(conf, DictConfig):
        # validate placement of standard directives before the processing loop
        def is_directive(k):
            return (
                k in ("_include", "_use", "_scrub")
                or k.startswith("_include_")
                or k.startswith("_use_")
                or k.startswith("_scrub_")
            )

        conf_keys = list(conf.keys())
        first_non_dir = next((i for i, k in enumerate(conf_keys) if not is_directive(k)), None)
        last_non_post = None
        for i, k in enumerate(conf_keys):
            if k not in ("_include_post", "_use_post", "_scrub_post"):
                last_non_post = i
        for i, key in enumerate(conf_keys):
            if key in ("_include", "_use"):
                if first_non_dir is not None and i > first_non_dir:
                    raise ConfigurattError(
                        f"{errloc}: '{key}' must appear at the top of the mapping before any content keys; "
                        f"use '_{key.lstrip('_')}_<suffix>' for mid-mapping placement"
                    )
            elif key in ("_include_post", "_use_post"):
                if last_non_post is not None and i < last_non_post:
                    raise ConfigurattError(
                        f"{errloc}: '{key}' must appear at the bottom of the mapping after all content keys"
                    )

        # since _use and _include statements can be nested, keep on processing until all are resolved
        updated = True
        recurse = 0

        while updated:
            updated = False
            # check for infinite recursion
            recurse += 1
            if recurse > 20:
                raise ConfigurattError(f"{errloc}: recursion limit exceeded, check your _use and _include statements")

            # All _include/_use directives (bare, suffixed, and _post) use the same positional-insertion
            # semantics: directives appearing later in the mapping have higher priority than earlier ones.
            # Snapshot key order up front; helper functions pop their directive keys from conf as they run.
            orig_keys = list(conf.keys())
            loaded_directives = {}

            if includes:
                # helper function: process includes recursively
                def process_include_directive(include_files: List[str], keyword: str, directive: Any, subpath=None):
                    if isinstance(directive, str):
                        include_files.append(directive if subpath is None else f"{subpath}/{directive}")
                    elif isinstance(directive, (tuple, list, ListConfig)):
                        for dir1 in directive:
                            process_include_directive(include_files, keyword, dir1, subpath)
                    elif isinstance(directive, DictConfig):
                        for key, value in directive.items_ex():
                            process_include_directive(
                                include_files, keyword, value, subpath=key if subpath is None else f"{subpath}/{key}"
                            )
                    else:
                        raise ConfigurattError(f"{errloc}: {keyword} contains invalid entry of type {type(directive)}")

                # helper function: load list of include files, returns accumulated DictConfig
                def load_include_files(keyword):
                    # pop include directive, return if None
                    include_directive = pop_conf(conf, keyword, None)
                    if include_directive is None:
                        return None
                    # get corresponding _scrub directive (_include → _scrub, _include_X → _scrub_X)
                    scrub_key = "_scrub" if keyword == "_include" else "_scrub_" + keyword[len("_include_") :]
                    scrub = pop_conf(conf, scrub_key, None)
                    if isinstance(scrub, str):
                        scrub = [scrub]

                    include_files = []
                    process_include_directive(include_files, keyword, include_directive)

                    accum_incl_conf = OmegaConf.create()

                    # load includes
                    for incl in include_files:
                        if not incl:
                            raise ConfigurattError(f"{errloc}: empty {keyword} specifier")
                        # check for [flags] at end of specifier
                        match = re.match(r"^(.*)\[(.*)\]$", incl)
                        if match:
                            incl = match.group(1)
                            flags = set([x.strip().lower() for x in match.group(2).split(",")])
                            warn = "warn" in flags
                            optional = "optional" in flags
                        else:
                            flags = {}
                            warn = optional = False

                        # helper function -- finds given include file (including trying an implicit .yml or .yaml
                        # extension) returns full name of file if found, else return None if include is optional,
                        # else adds fail record and raises exception. If opt=True, this is stronger than optional
                        # (no warnings raised)
                        def find_include_file(path: str, opt: bool = False):
                            # if path already has an extension, only try the pathname itself
                            if os.path.splitext(path)[1]:
                                paths = [path]
                            # else try the pathname itself, plus implicit extensions
                            else:
                                paths = [path] + [path + ext for ext in IMPLICIT_EXTENSIONS]
                            # now try all of them and return a matching one if found
                            for path in paths:
                                if os.path.isfile(path):
                                    return path
                            # end of loop with no matching files? Raise error
                            else:
                                if opt:
                                    return None
                                elif optional:
                                    dependencies.add_fail(FailRecord(path, pathname, warn=warn))
                                    if warn:
                                        print(f"Warning: unable to find optional include {path}")
                                    return None
                                raise ConfigurattError(f"{errloc}: {keyword} {path} does not exist")

                        # check for (location)filename.yaml or (location)/filename.yaml style
                        match = re.match(r"^\((.+)\)/?(.+)$", incl)
                        if match:
                            modulename, filename = match.groups()
                            if modulename.startswith("."):
                                filename = os.path.join(os.path.dirname(pathname), modulename, filename)
                                filename = find_include_file(filename)
                                if filename is None:
                                    continue
                            else:
                                try:
                                    mod = importlib.import_module(modulename)
                                except ImportError as exc:
                                    if optional:
                                        dependencies.add_fail(
                                            FailRecord(incl, pathname, modulename=modulename, fname=filename, warn=warn)
                                        )
                                        if warn:
                                            print(f"Warning: unable to import module for optional include {incl}")
                                        continue
                                    raise ConfigurattError(
                                        f"{errloc}: {keyword} {incl}: can't import {modulename} ({exc})"
                                    )
                                if mod.__file__ is not None:
                                    path = os.path.dirname(mod.__file__)
                                else:
                                    path = getattr(mod, "__path__", None)
                                    if path is None:
                                        if optional:
                                            dependencies.add_fail(
                                                FailRecord(
                                                    incl, pathname, modulename=modulename, fname=filename, warn=warn
                                                )
                                            )
                                            if warn:
                                                print(
                                                    f"Warning: unable to resolve path for optional include {incl}, "
                                                    f"does {modulename} contain __init__.py?"
                                                )
                                            continue
                                        raise ConfigurattError(
                                            f"{errloc}: {keyword} {incl}: can't resolve path for {modulename}, does "
                                            f"it contain __init__.py?"
                                        )
                                    path = path[0]

                                filename = find_include_file(os.path.join(path, filename))
                                if filename is None:
                                    continue
                        else:
                            # expand ~
                            incl = os.path.expanduser(incl)
                            # absolute path -- one candidate
                            if os.path.isabs(incl):
                                filename = find_include_file(incl)
                                if filename is None:
                                    continue
                            # relative path -- scan PATH for candidates
                            else:
                                paths = [".", os.path.dirname(pathname)] + PATH
                                candidates = [os.path.join(p, incl) for p in paths]
                                for filename in candidates:
                                    filename = find_include_file(filename, opt=True)
                                    if filename is not None:
                                        break
                                # none found in candidates -- process error
                                else:
                                    if optional:
                                        dependencies.add_fail(FailRecord(incl, pathname, warn=warn))
                                        if warn:
                                            print(f"Warning: unable to find optional include {incl}")
                                        continue
                                    raise ConfigurattError(f"{errloc}: {keyword} {incl} not found in {':'.join(paths)}")

                        # check for recursion
                        for path in include_stack:
                            if os.path.samefile(path, filename):
                                raise ConfigurattError(f"{errloc}: {filename} is included recursively")
                        # load included file
                        incl_conf, deps = load(
                            filename,
                            location=location,
                            name=f"{filename}, included from {name}",
                            includes=True,
                            include_stack=include_stack,
                            use_cache=use_cache,
                            use_sources=None,
                        )  # do not expand _use statements in included files, this is done below

                        dependencies.update(deps)
                        if include_path is not None:
                            incl_conf[include_path] = filename

                        # accumulate included config so that later includes override earlier ones
                        accum_incl_conf = OmegaConf.unsafe_merge(accum_incl_conf, incl_conf)

                    if scrub:
                        try:
                            _scrub_subsections(accum_incl_conf, scrub)
                        except ConfigurattError as exc:
                            raise ConfigurattError(f"{errloc}: error scrubbing {', '.join(scrub)}", exc)

                    return accum_incl_conf

                for key in orig_keys:
                    if key == "_include" or key.startswith("_include_"):
                        loaded_directives[key] = load_include_files(key)

            if use_sources is not None:

                def load_use_sections(keyword):
                    merge_sections = pop_conf(conf, keyword, None)
                    if merge_sections is None:
                        return None
                    # get corresponding _scrub directive (_use → _scrub, _use_X → _scrub_X)
                    scrub_key = "_scrub" if keyword == "_use" else "_scrub_" + keyword[len("_use_") :]
                    scrub = pop_conf(conf, scrub_key, None)
                    if type(merge_sections) is str:
                        merge_sections = [merge_sections]
                    elif not isinstance(merge_sections, Sequence):
                        raise TypeError(f"invalid {name}.{keyword} directive of type {type(merge_sections)}")
                    if len(merge_sections):
                        # resolve each raw name to an absolute name (supporting relative references)
                        raw_names = list(merge_sections)
                        abs_names = [_abs_use_name(n, location) for n in raw_names]
                        sections = [_lookup_name(n, *use_sources) for n in abs_names]
                        # resolve each section using *its own* location so that any relative
                        # _use references inside the imported section resolve correctly
                        resolved = []
                        for sect_name, sect in zip(abs_names, sections):
                            sect_resolved, deps = resolve_config_refs(
                                sect.copy(),
                                pathname=pathname,
                                name=name,
                                location=sect_name,
                                includes=includes,
                                use_sources=use_sources,
                                use_cache=use_cache,
                                include_path=include_path,
                            )
                            dependencies.update(deps)
                            resolved.append(sect_resolved)
                        base = resolved[0]
                        for s in resolved[1:]:
                            base.merge_with(s)
                        if scrub:
                            try:
                                _scrub_subsections(base, scrub)
                            except ConfigurattError as exc:
                                raise ConfigurattError(f"{errloc}: error scrubbing {', '.join(scrub)}", exc)
                        return base
                    return None

                for key in orig_keys:
                    if (key == "_use" or key.startswith("_use_")) and key not in loaded_directives:
                        loaded_directives[key] = load_use_sections(key)

            # Rebuild conf: merge each directive's content at its position in the key order.
            # Merges are applied in mapping order, so later entries override earlier ones —
            # uniform positional semantics for all directive forms (_include, _include_SUFFIX,
            # _include_post, _use, _use_SUFFIX, _use_post). Full (deep) merge semantics are
            # preserved so that nested keys are handled correctly.
            if loaded_directives:
                updated = True
                # Collect parts in key order, then merge once — O(N) instead of O(N²).
                parts = []
                for key in orig_keys:
                    if key in loaded_directives:
                        loaded = loaded_directives[key]
                        if loaded is not None:
                            parts.append(loaded)
                    elif key in conf:
                        parts.append(OmegaConf.masked_copy(conf, [key]))
                conf = OmegaConf.unsafe_merge(*parts) if parts else OmegaConf.create()
                if selfrefs:
                    use_sources[0] = conf

        # Detect orphaned _scrub / _scrub_<suffix> keys: their companion directive was
        # never present (or was misspelled), so they were never popped during processing.
        # Exception: if the companion directive is still in conf, processing was simply
        # disabled (includes=False or use_sources=None) — not an error in that case.
        for key in conf.keys():
            if key == "_scrub" or key.startswith("_scrub_"):
                if key == "_scrub":
                    has_companion = "_include" in conf or "_use" in conf
                else:
                    suffix = key[len("_scrub_") :]
                    has_companion = f"_include_{suffix}" in conf or f"_use_{suffix}" in conf
                if not has_companion:
                    raise ConfigurattError(f"{errloc}: '{key}' has no matching _include or _use directive")

        # recurse into content
        for key, value in conf.items_ex(resolve=False):
            if isinstance(value, (DictConfig, ListConfig)):
                value1, deps = resolve_config_refs(
                    value,
                    pathname=pathname,
                    name=name,
                    location=f"{location}.{key}" if location else key,
                    includes=includes,
                    include_stack=include_stack,
                    use_sources=use_sources,
                    use_cache=use_cache,
                    include_path=include_path,
                )
                dependencies.update(deps)
                # reassigning is expensive, so only do it if there was an actual change
                if value1 is not value:
                    conf[key] = value1

    # recurse into lists
    elif isinstance(conf, ListConfig):
        # recurse in
        for i, value in enumerate(conf._iter_ex(resolve=False)):
            if isinstance(value, (DictConfig, ListConfig)):
                value1, deps = resolve_config_refs(
                    value,
                    pathname=pathname,
                    name=name,
                    location=f"{location or ''}[{i}]",
                    includes=includes,
                    include_stack=include_stack,
                    use_sources=use_sources,
                    use_cache=use_cache,
                    include_path=include_path,
                )
                dependencies.update(deps)
                if value1 is not value:
                    conf[i] = value

    return conf, dependencies
