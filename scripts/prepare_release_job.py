"""Normalize legacy job setting names without changing resources or secret references."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from prepare_cloud_run_cutover import (
    SENSITIVE_ENV_MARKERS,
    SENSITIVE_EXCEPTIONS,
    _canonical_env_name,
    _clean_metadata,
    _rewrite_required_secrets,
    _uses_secret_reference,
)


def prepare_job(source: dict[str, Any], image: str) -> dict[str, Any]:
    job = copy.deepcopy(source)
    job.pop("status", None)
    _clean_metadata(job["metadata"])
    outer = job["spec"]["template"]
    _clean_metadata(outer.setdefault("metadata", {}))
    template = outer["spec"]["template"]
    _clean_metadata(template.setdefault("metadata", {}))
    containers = template["spec"]["containers"]
    if len(containers) != 1:
        raise ValueError("Expected one application job container")
    container = containers[0]
    mapped: dict[str, dict[str, Any]] = {}
    for item in container.get("env", []):
        name = _canonical_env_name(item["name"])
        if name is None:
            continue
        if name in mapped:
            raise ValueError("Conflicting legacy and neutral environment names")
        if (
            name not in SENSITIVE_EXCEPTIONS
            and any(marker in name for marker in SENSITIVE_ENV_MARKERS)
            and "value" in item
            and not _uses_secret_reference(item)
        ):
            raise ValueError("Plaintext sensitive environment value is forbidden")
        item["name"] = name
        if name == "AD_ANALYZER_REQUIRED_SECRET_NAMES" and "value" in item:
            item["value"] = _rewrite_required_secrets(item["value"])
        mapped[name] = item
    container["env"] = list(mapped.values())
    container["image"] = image
    return job


if __name__ == "__main__":
    source = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(json.dumps(prepare_job(source, sys.argv[3])))
