# Forward, Group, Word, Optional, alphas, alphanums, nums, ZeroOrMore, Literal, sglQuotedString, dblQuotedString
from rich import print


def test_parser():
    from scabha.evaluator import construct_parser

    expr = construct_parser()

    for string in [
        "a.b + b.c - c.d",
        "a.b + b.c * c.d",
        "a.b + -b.c",
        "a.b <= 0",
        "a.b",
        "IFSET(a.b)",
        "a.b[c.d]",
    ]:
        print(f"\n\n\n=====================\nExpression: {string}\n")
        a = expr.parse_string(string, parse_all=True)
        print(f"\n\n\n{a.getName()}")
        print(a.dump())
