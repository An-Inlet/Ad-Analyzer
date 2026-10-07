"""Purpose- and checkpoint-bound encryption using the existing Shopify vault."""

from app.commerce.acquisition_contracts import Checkpoint, NativeHandles
from app.commerce.evidence import digest
from app.commerce.independent_contracts import ScanRequest, ScanUnavailable
from app.shopify.security import ShopifyError, Vault


def _purpose(request: ScanRequest, checkpoint: Checkpoint) -> str:
    if checkpoint.request_digest != request.request_digest:
        raise ScanUnavailable("acquisition_checkpoint_invalid")
    return digest(
        [
            "inlet.acquisition-native-handles.v1",
            request.scope.workspace_id,
            request.scope.store_id,
            request.acquisition_id,
            request.request_digest,
            checkpoint.phase,
            checkpoint.sequence,
            checkpoint.digest(),
        ]
    )


def seal_handles(
    vault: Vault, request: ScanRequest, checkpoint: Checkpoint, handles: NativeHandles
) -> str:
    handles = NativeHandles.model_validate_json(handles.model_dump_json())
    value = vault.seal(
        request.scope.workspace_id, _purpose(request, checkpoint), handles.model_dump(mode="json")
    )
    if len(value) > 16384:
        raise ScanUnavailable("acquisition_handle_limit")
    return value


def open_handles(
    vault: Vault, request: ScanRequest, checkpoint: Checkpoint, value: str
) -> NativeHandles:
    try:
        if len(value) > 16384:
            raise ValueError("size")
        return NativeHandles.model_validate(
            vault.open(request.scope.workspace_id, _purpose(request, checkpoint), value)
        )
    except (ShopifyError, ValueError, TypeError):
        raise ScanUnavailable("acquisition_checkpoint_invalid") from None
