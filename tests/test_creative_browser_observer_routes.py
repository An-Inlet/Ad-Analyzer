"""Closed, payload-free browser route labels; no live ASGI invocation."""

import pytest

from tests.creative_browser_observer import fixed_detail, route_class

ROOT = "/api/customer/v1/workspaces/12/planning"
PLAN = ROOT + "/plans/" + "a" * 32


@pytest.mark.parametrize(
    "method,path,label",
    [
        ("POST", PLAN + "/generate", "generate"),
        ("GET", PLAN, "current"),
        ("GET", PLAN + "/versions", "versions"),
        ("POST", ROOT + "/google-budget-owners", "owner_discovery"),
        ("POST", ROOT + "/plans", "create"),
        ("POST", PLAN + "/inputs", "revise"),
        ("GET", PLAN + "/versions/1", "version"),
        ("GET", PLAN + "/export", "export"),
        *[("GET", ROOT + "/plans/requests/" + operation + "/abcdefgh", "request_receipt")
          for operation in ("create", "revise", "generate", "decide", "assert_applied")],
        ("GET", ROOT + "/plans/requests/create/" + "A_9-" * 32, "request_receipt"),
    ],
)
def test_closed_route(method: str, path: str, label: str) -> None:
    assert route_class(path, method) == label
    assert route_class(path, "DELETE") is None
    assert route_class(path + "?token=private", method) is None
    assert route_class(path + "/", method) is None


@pytest.mark.parametrize(
    "path,method",
    [
        (ROOT + "/plans/requests/create/short", "GET"),
        (ROOT + "/plans/requests/create/" + "x" * 129, "GET"),
        (ROOT + "/plans/requests/unknown/abcdefgh", "GET"),
        (ROOT + "/plans/requests/create/abcd%20ef", "GET"),
        (ROOT + "/plans/requests/create/abcdefgh", "POST"),
        (PLAN + "/versions/0", "GET"),
        (PLAN + "/versions/01", "GET"),
        (PLAN + "/versions/-1", "GET"),
        (PLAN + "/versions/1", "POST"),
        (PLAN.replace("a" * 32, "A" * 32), "GET"),
        (PLAN.replace("a" * 32, "a" * 31) + "/inputs", "POST"),
        (ROOT + "/google-budget-owners", "GET"),
        (ROOT.replace("/12/", "/foreign/") + "/plans", "POST"),
        (PLAN + "/export", "POST"),
    ],
)
def test_unrecognized_route(path: str, method: str) -> None:
    assert route_class(path, method) is None


def test_detail_allowlist_never_retains_unknown_payload() -> None:
    assert fixed_detail("owner review differs from actual collected evidence") == (
        "owner review differs from actual collected evidence"
    )
    assert fixed_detail("planning_authority_expired") == "planning_authority_expired"
    assert fixed_detail(None) is None
    for value in ("secret text", {"detail": "private"}, ["private"], 409):
        assert fixed_detail(value) == "unlisted_server_detail"
