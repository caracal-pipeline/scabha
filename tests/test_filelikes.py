from typing import Dict, List, Optional, Set, Tuple, Union

import pytest

from scabha.basetypes import MS, URI, Directory, File, get_filelikes


@pytest.fixture(scope="module", params=[File, URI, Directory, MS])
def templates(request):
    ft = request.param

    TEMPLATES = (
        (Tuple, (), set()),
        (Tuple[int, ...], [1, 2], set()),
        (Tuple[ft, ...], ("foo", "bar"), {"foo", "bar"}),
        (Tuple[ft, str], ("foo", "bar"), {"foo"}),
        (Dict[str, int], {"a": 1, "b": 2}, set()),
        (Dict[str, ft], {"a": "foo", "b": "bar"}, {"foo", "bar"}),
        (Dict[ft, str], {"foo": "a", "bar": "b"}, {"foo", "bar"}),
        (List[ft], [], set()),
        (List[int], [1, 2], set()),
        (List[ft], ["foo", "bar"], {"foo", "bar"}),
        (Set[ft], set(), set()),
        (Set[int], {1, 2}, set()),
        (Set[ft], {"foo", "bar"}, {"foo", "bar"}),
        (Union[str, List[ft]], "foo", set()),
        (Union[str, List[ft]], ["foo"], {"foo"}),
        (Union[str, Tuple[ft]], "foo", set()),
        (Union[str, Tuple[ft]], ("foo",), {"foo"}),
        (Optional[ft], None, set()),
        (Optional[ft], "foo", {"foo"}),
        (Optional[Union[ft, int]], 1, set()),
        (Optional[Union[ft, int]], "foo", {"foo"}),
        (Dict[str, Tuple[ft, str]], {"a": ("foo", "bar")}, {"foo"}),
    )

    return TEMPLATES


def test_get_filelikes(templates):
    for dt, v, res in templates:
        assert get_filelikes(dt, v) == res, f"Failed for dtype {dt} and value {v}."


@pytest.fixture(scope="module", params=[File, URI, Directory, MS])
def file_type(request):
    return request.param


def test_is_file_type_unwraps_optional(file_type):
    """Optional[File]-style inputs must register as file-typed, or they become
    invisible to stimela's skip_if_outputs freshness tracking (issue #40)."""
    from scabha.basetypes import is_file_list_type, is_file_type

    ft = file_type
    assert is_file_type(ft)
    assert is_file_type(Optional[ft])
    assert is_file_list_type(List[ft])
    assert is_file_list_type(Optional[List[ft]])
    # non-file types stay non-file, wrapped or not
    assert not is_file_type(str)
    assert not is_file_type(Optional[str])
    assert not is_file_list_type(Optional[List[int]])
    # genuine multi-type unions are not unwrapped
    assert not is_file_type(Union[ft, int])
    assert not is_file_list_type(Union[List[ft], int])
