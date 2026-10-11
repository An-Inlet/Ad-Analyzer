"""Bounded route-only diagnostic; never retain identifiers or response documents."""

import re

_ROUTE = re.compile(
    r"^/api/customer/v1/workspaces/[0-9]+/planning/plans/[a-f0-9]{32}"
    r"(?P<suffix>/generate|/versions)?$"
)

_ROOT = r"/api/customer/v1/workspaces/[0-9]+/planning"
_PLAN = _ROOT + r"/plans/[a-f0-9]{32}"
_EXTRA_ROUTES = (
    ("POST", re.compile(_ROOT + r"/google-budget-owners"), "owner_discovery"),
    ("POST", re.compile(_ROOT + r"/plans"), "create"),
    ("POST", re.compile(_PLAN + r"/inputs"), "revise"),
    ("GET", re.compile(_PLAN + r"/versions/[1-9][0-9]*"), "version"),
    ("GET", re.compile(_PLAN + r"/export"), "export"),
    (
        "GET",
        re.compile(
            _ROOT + r"/plans/requests/(?:create|revise|generate|decide|assert_applied)"
            r"/[A-Za-z0-9_-]{8,128}"
        ),
        "request_receipt",
    ),
)

FIXED_DETAILS = frozenset(
    (
        "Account diagnostics could not be completed. Check your connection and try again.",
        "Planning evidence changed. Read current sources again.",
        "Qualified reporting evidence changed",
        "Selected target changed. Read the current catalog and select again.",
        "The account changed during maintenance. Read again.",
        "The account changed during this read. Read again.",
        "The exact catalog selection is unavailable. Read fresh targets and explicitly "
        "save a new input revision before generating a plan.",
        "This catalog expired before it could be saved. Read again.",
        "candidate creative proof differs from actual read bundle",
        "candidate does not match generation",
        "candidate evidence differs from actual read bundle",
        "candidate generation predates original creative collection",
        "candidate selected proof differs from actual read bundle",
        "candidate target differs from actual owned catalog",
        "configured planning generator changed",
        "confirm the current goal before planning",
        "confirmed goal changed",
        "confirmed goal commerce source unavailable",
        "confirmed goal source unavailable",
        "creative image source changed",
        "creative paired evidence required",
        "creative planning evidence unavailable",
        "creative proof differs from collected evidence",
        "event actor or plan inputs changed",
        "event chain head changed",
        "event receipt unavailable",
        "event sequence changed",
        "explicit creative media store required",
        "generation evidence expired",
        "generation head changed",
        "generation input or version changed",
        "generation parent changed",
        "generation privacy changed",
        "input actor or revision mismatch",
        "legacy reporting evidence required",
        "manual report already retracted",
        "nested planning read context unavailable",
        "new plan cannot have a prior version",
        "no manual report to retract",
        "original generation actor changed",
        "original generation session changed",
        "plan evidence expired",
        "plan evidence expired or changed",
        "plan input or version changed",
        "plan version or action binding changed",
        "plan version or event sequence changed",
        "plan_progress_integrity_unavailable",
        "planning evidence does not match generation",
        "planning evidence policy differs",
        "planning input source changed",
        "planning_authority_expired",
        "owner review differs from actual collected evidence",
        "request key belongs to another plan",
        "request key is bound to different input",
        "requested-window evidence required",
        "selected advertising source changed",
        "selected creative media unavailable",
        "selected paired evidence required",
        "selected plan historical integrity unavailable",
        "selected reporting integrity unavailable",
        "unknown configured planning policy",
        "unknown planning policy or generator",
    )
)


def route_class(path: str, method: str) -> str | None:
    match = _ROUTE.fullmatch(path)
    if match is None:
        return next(
            (label for verb, pattern, label in _EXTRA_ROUTES
             if method == verb and pattern.fullmatch(path)),
            None,
        )
    suffix = match.group("suffix")
    if method == "POST" and suffix == "/generate":
        return "generate"
    if method == "GET" and suffix is None:
        return "current"
    if method == "GET" and suffix == "/versions":
        return "versions"
    return None


def fixed_detail(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and value in FIXED_DETAILS else "unlisted_server_detail"
