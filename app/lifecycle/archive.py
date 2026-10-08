"""Bounded, ephemeral, consistent-snapshot customer archive. No provider reads."""

import hashlib
import io
import json
import re
import tarfile
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import Engine, Text, case, cast, func, literal, select
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MAX_LIBRARY_BYTES, MAX_MEDIA_BYTES, MediaStore
from app.database.session import Base
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import exclusion, fields, serialize, validation_fields
from app.lifecycle.inventory import predicate, verify_registry
from app.lifecycle.registry import PRIVATE_STAGING_TABLES, TABLES
from app.planning_documents.storage import MAX_PLANNING_ROW_BYTES, PLANNING_TABLES

MAX_ARCHIVE_BYTES = 192 * 1024 * 1024
MAX_DATA_BYTES = 32 * 1024 * 1024

MAX_ROW_BYTES = 1024 * 1024
MAX_ROWS = 100_000
MAX_SECONDS = 120
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4"}


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def build(
    engine: Engine,
    wid: int,
    request_id: str,
    revision: int,
    store: Callable[[], MediaStore],
    authorize: Callable[[], None],
    capture_privacy: Callable[[Session], dict[str, Any]],
) -> tuple[BinaryIO, dict[str, Any]]:
    """Build before headers; caller owns the returned anonymous file, including on disconnect."""
    verify_registry()
    started = time.monotonic()
    output = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115 — ownership transfers to Download
    total_rows = total_data = total_media = 0
    sections: list[dict[str, Any]] = []
    media: list[dict[str, Any]] = []
    omissions: list[dict[str, Any]] = []

    def checkpoint() -> None:
        if time.monotonic() - started >= MAX_SECONDS:
            raise ValueError("export build deadline exceeded")
        authorize()

    def add(archive: tarfile.TarFile, name: str, source: BinaryIO, size: int) -> None:
        if output.tell() + size + 2048 > MAX_ARCHIVE_BYTES:
            raise ValueError("export archive exceeds bound")
        info = tarfile.TarInfo(name)
        info.size, info.mode, info.mtime = size, 0o600, 0
        source.seek(0)
        archive.addfile(info, source)

    try:
        checkpoint()
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
            elif engine.dialect.name != "sqlite":
                raise ValueError("unsupported export snapshot database")
            with connection.begin():
                if engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN")
                else:
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '15000ms'")
                # First SELECT establishes the snapshot, before any section or storage IO.
                connection.execute(
                    select(Base.metadata.tables["workspaces"].c.id).where(
                        Base.metadata.tables["workspaces"].c.id == wid
                    )
                ).first()
                as_of = datetime.now(UTC).isoformat()
                with (
                    Session(bind=connection) as snapshot,
                    tarfile.open(fileobj=output, mode="w") as archive,
                ):
                    privacy = capture_privacy(snapshot)
                    scope = LifecycleScopeV1(workspace_id=wid)
                    for name, policy in TABLES.items():
                        checkpoint()
                        if policy.scope in {"identity_global", "platform_global", "unclassified"}:
                            omissions.append({"table": name, "reason": policy.scope})
                            continue
                        if name in PRIVATE_STAGING_TABLES:
                            omissions.append(
                                {"table": name, "reason": "private_acquisition_staging"}
                            )
                            continue
                        table = Base.metadata.tables[name]
                        selected = fields(name)
                        validated = tuple(dict.fromkeys((*selected, *validation_fields(name))))
                        excluded = {
                            key: exclusion(name, key)
                            for key in table.c.keys()  # noqa: SIM118 — ColumnCollection iteration yields columns
                            if key not in selected
                        }
                        unsupported = {
                            key
                            for key, why in excluded.items()
                            if why == "unsupported_customer_field"
                        }
                        count, size, digest = 0, 0, hashlib.sha256()
                        with tempfile.TemporaryFile(mode="w+b") as section:
                            # Conservative UTF-8 bound before driver materialization.
                            row_limit = (
                                MAX_PLANNING_ROW_BYTES if name in PLANNING_TABLES else MAX_ROW_BYTES
                            )
                            oversized = (
                                sum(
                                    [
                                        func.coalesce(func.length(cast(table.c[key], Text)), 0) * 4
                                        for key in validated
                                    ],
                                    start=literal(0),
                                )
                                > row_limit
                            )
                            rows = snapshot.execute(
                                select(
                                    *(
                                        case((oversized, None), else_=table.c[key]).label(key)
                                        for key in validated
                                    ),
                                    oversized.label("_export_oversized"),
                                )
                                .where(predicate(name, scope))
                                .order_by(*table.primary_key.columns)
                                .execution_options(yield_per=1)
                            ).mappings()
                            try:
                                for row in rows:
                                    checkpoint()
                                    total_rows += 1
                                    if total_rows > MAX_ROWS:
                                        raise ValueError("export row limit exceeded")
                                    if row["_export_oversized"]:
                                        raise ValueError("export stored row exceeds bound")
                                    projected, missing = serialize(name, dict(row), db=snapshot)
                                    unsupported.update(missing)
                                    data = encoded(projected) + b"\n"
                                    total_data += len(data)
                                    if len(data) > row_limit or total_data > MAX_DATA_BYTES:
                                        raise ValueError("export data bound exceeded")
                                    section.write(data)
                                    digest.update(data)
                                    count, size = count + 1, size + len(data)
                                    if name == "customer_media_objects":
                                        identifier, sha, length, mime = (
                                            row["id"],
                                            row["sha256"],
                                            row["size"],
                                            row["mime"],
                                        )
                                        if (
                                            not re.fullmatch(r"[a-f0-9]{32}", identifier)
                                            or not re.fullmatch(r"[a-f0-9]{64}", sha)
                                            or mime not in EXTENSIONS
                                            or not 0 < length <= MAX_MEDIA_BYTES
                                        ):
                                            raise ValueError("invalid media metadata")
                                        total_media += length
                                        if total_media > MAX_LIBRARY_BYTES:
                                            raise ValueError("export media bound exceeded")
                                        payload = store().read_exact(wid, sha, length)
                                        checkpoint()
                                        if (
                                            len(payload) != length
                                            or hashlib.sha256(payload).hexdigest() != sha
                                        ):
                                            raise ValueError("media integrity mismatch")
                                        path = f"media/{identifier}.{EXTENSIONS[mime]}"
                                        add(archive, path, io.BytesIO(payload), length)
                                        media.append({"path": path, "sha256": sha, "bytes": length})
                            finally:
                                rows.close()
                            path = f"data/{name}.jsonl"
                            add(archive, path, section, size)
                        sections.append(
                            {
                                "schema_version": f"inlet.export.{name}.v1",
                                "path": path,
                                "rows": count,
                                "bytes": size,
                                "sha256": digest.hexdigest(),
                                "excluded_fields": excluded,
                                "unsupported_fields": sorted(unsupported),
                                "complete": not unsupported,
                            }
                        )
                    manifest = {
                        "schema_version": "inlet.customer-export.v1",
                        "scope": scope.model_dump(),
                        "request_id": request_id,
                        "snapshot_revision": revision,
                        "snapshot_as_of": as_of,
                        "sections": sections,
                        "media": media,
                        "excluded_tables": omissions,
                        "supported_customer_data_complete": all(
                            section["complete"] for section in sections
                        ),
                        "media_archive_complete": True,
                        "all_stored_workspace_data_complete": not any(
                            omission["reason"] == "unclassified" for omission in omissions
                        )
                        and all(section["complete"] for section in sections),
                        "privacy_fence": privacy,
                        "delivery": "unconfirmed",
                        "retained_artifact": False,
                    }
                    data = encoded(manifest)
                    add(archive, "manifest.json", io.BytesIO(data), len(data))
        checkpoint()
        if output.tell() > MAX_ARCHIVE_BYTES:
            raise ValueError("export archive exceeds bound")
        output.seek(0)
        return output, manifest
    except BaseException:
        output.close()
        raise
