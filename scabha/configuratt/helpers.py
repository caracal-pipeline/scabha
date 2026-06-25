import fnmatch
from typing import Dict, List, Optional, Union

from omegaconf.omegaconf import DictConfig

from .common import ConfigurattError, pop_conf


def _lookup_nameseq(name_seq: List[str], source_dict: Dict):
    """Internal helper: looks up nested item ('a', 'b', 'c') in a nested dict

    Parameters
    ----------
    name_seq : List[str]
        sequence of keys to look up
    source_dict : Dict
        nested dict

    Returns
    -------
    Any
        value if found, else None
    """
    source = source_dict
    names = list(name_seq)
    while names:
        source = source.get(names.pop(0), None)
        if source is None:
            return None
    return source


def _lookup_name(name: str, *sources: List[Dict]):
    """Internal helper: looks up a nested item ("a.b.c") in a list of dicts

    Parameters
    ----------
    name : str
        section name to look up, e.g. "a.b.c"

    Returns
    -------
    Any
        first matching item found

    Raises
    ------
    NameError
        if matching item is not found
    """
    name_seq = name.split(".")
    for source in sources:
        result = _lookup_nameseq(name_seq, source)
        if result is not None:
            return result
    raise ConfigurattError(f"unknown key {name}")


def _abs_use_name(name: str, location: Optional[str]) -> str:
    """Compute the absolute dotted name for a _use reference (without looking it up).

    Parameters
    ----------
    name : str
        raw _use name; may start with dots for relative references
    location : Optional[str]
        dotted path of the current mapping

    Returns
    -------
    str
        absolute dotted name
    """
    if not name.startswith("."):
        return name

    # count leading dots
    dots = len(name) - len(name.lstrip("."))
    remainder = name[dots:]

    if not remainder:
        raise ConfigurattError(f"relative _use reference '{name}' has no target name after the dots")

    if not location:
        raise ConfigurattError(f"relative _use reference '{name}' is not valid at top level")

    if "[" in location:
        raise ConfigurattError(f"relative _use reference '{name}' is not valid inside a list (location: '{location}')")

    parts = location.split(".")
    if dots > len(parts):
        raise ConfigurattError(f"relative _use reference '{name}' goes above the top level from '{location}'")

    ancestor_parts = parts[:-dots] if dots < len(parts) else []
    return ".".join(ancestor_parts + [remainder])


def _resolve_use_name(name: str, location: Optional[str], *sources: List[Dict]):
    """Look up a _use name in sources, supporting relative references (leading dots).

    A relative reference starts with one or more dots:
      .foo    -- sibling of the current mapping (go up 1 level, then look up 'foo')
      ..foo   -- go up 2 levels, then look up 'foo'

    Parameters
    ----------
    name : str
        name to look up; may start with dots for relative references
    location : Optional[str]
        dotted path of the current mapping (e.g. "recipe.steps.step2")
    sources : List[Dict]
        config sources to search

    Returns
    -------
    Any
        the looked-up section
    """
    return _lookup_name(_abs_use_name(name, location), *sources)


def _flatten_subsections(conf, depth: int = 1, sep: str = "__"):
    """Recursively flattens subsections in a DictConfig (modifying in place)
    A structure such as
        a:
            b: 1
            c: 2
    Becomes
        a__b: 1
        a__c: 2

    Args:
        conf (DictConfig): config to flatten
        depth (int):       depth to which to flatten. Default is 1 level.
        sep (str):         separator to use, default is "__"
    """
    subsections = [(key, value) for key, value in conf.items() if isinstance(value, DictConfig)]
    for name, subsection in subsections:
        pop_conf(conf, name)
        if depth > 1:
            _flatten_subsections(subsection, depth - 1, sep)
        for key, value in subsection.items():
            conf[f"{name}{sep}{key}"] = value


def _scrub_subsections(conf: DictConfig, scrubs: Union[str, List[str]]):
    """
    Scrubs named subsections from a config.

    Args:
        conf (DictConfig): config to scrub
        scrubs (Union[str, List[str]]): sections to remove (can include dots to remove nested sections)
    """
    if isinstance(scrubs, str):
        scrubs = [scrubs]

    for scrub in scrubs:
        if "." in scrub:
            name, remainder = scrub.split(".", 1)
        else:
            name, remainder = scrub, None
        # apply name as pattern
        is_pattern = "*" in name or "?" in name
        matches = fnmatch.filter(conf.keys(), name)
        if not matches:
            # if no matches to pattern, it's ok, otherwise raise error
            if is_pattern:
                return
            raise ConfigurattError(f"no entry matching '{name}'")
        # recurse into or remove matching entries
        for key in matches:
            if remainder:
                subconf = conf[key]
                if type(subconf) is DictConfig:
                    _scrub_subsections(subconf, remainder)
                elif not is_pattern:
                    raise ConfigurattError(f"'{name}' does not refer to a subsection")
            else:
                del conf[key]
