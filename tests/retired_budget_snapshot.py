"""Literal pre0085 budget producer source; never a fallback for other modes."""

import subprocess
import tarfile
from pathlib import Path

from tests.retired_snapshot import git

BUDGET_PIN = "745acee533638f6f937339110944454cd8ce2a83"
BUDGET_TREES = {
    "app": "e2abf13cbbca4f80001b2054da449360d0bfe5f2",
    "tests": "a4be5cd63965896d8f04cf2f43dbda0fa368bb82",
    "scripts": "c49d7769faa20df001536e6f819a1e1f7c860c57",
}


def extract_budget(root: Path, destination: Path) -> None:
    assert git(root, "rev-parse", BUDGET_PIN + "^{commit}") == BUDGET_PIN
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", BUDGET_PIN, "HEAD"],
                   check=True, timeout=30)
    for name, expected in BUDGET_TREES.items():
        assert git(root, "rev-parse", BUDGET_PIN + ":" + name) == expected
    destination.mkdir()
    archive = destination.parent / "historical-budget-source.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "-C", str(root), "archive", "--format=tar", BUDGET_PIN],
                       stdout=stream, check=True, timeout=60)
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    archive.unlink()
