import hashlib


def identifier_digest(workspace_id: int, namespace: str, value: str | None) -> str | None:
    """Return a deterministic workspace-bound digest without retaining the raw identifier."""
    if value is None:
        return None
    payload = f"ad-analyzer:v1\x1f{workspace_id}\x1f{namespace}\x1f{value}".encode()
    return hashlib.sha256(payload).hexdigest()
