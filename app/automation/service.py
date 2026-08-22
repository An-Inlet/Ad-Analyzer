from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.automation.catalog import (
    AUTOMATION_CONTROL_BY_KEY,
    AUTOMATION_CONTROL_DEFINITIONS,
    AutomationControlDefinition,
    AutomationControlKey,
)
from app.automation.models import (
    AutomationControlAudit,
    PlatformAutomationControl,
    WorkspaceAutomationControl,
)


class UnknownAutomationControlError(ValueError):
    """Fixed error for an unknown or unsupported control."""

    def __init__(self) -> None:
        super().__init__("Unknown automation control.")


@dataclass(frozen=True)
class AutomationControlState:
    key: str
    label: str
    description: str
    master_enabled: bool
    workspace_enabled: bool | None
    effective_enabled: bool
    external: bool


def control_key(value: str | AutomationControlKey) -> AutomationControlKey:
    try:
        return AutomationControlKey(value)
    except ValueError:
        raise UnknownAutomationControlError() from None


def control_definition(
    value: str | AutomationControlKey,
) -> AutomationControlDefinition:
    return AUTOMATION_CONTROL_BY_KEY[control_key(value)]


class AutomationControlService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def master_enabled(self, value: str | AutomationControlKey) -> bool:
        definition = control_definition(value)
        row = self.session.get(PlatformAutomationControl, definition.key.value)
        return row.enabled if row is not None else definition.default_enabled

    def workspace_enabled(
        self,
        workspace_id: int,
        value: str | AutomationControlKey,
    ) -> bool:
        definition = control_definition(value)
        if not definition.supports_workspace:
            raise UnknownAutomationControlError()
        row = self.session.get(
            WorkspaceAutomationControl,
            (workspace_id, definition.key.value),
        )
        return row.enabled if row is not None else definition.default_enabled

    def effective_enabled(
        self,
        workspace_id: int,
        value: str | AutomationControlKey,
    ) -> bool:
        definition = control_definition(value)
        if not definition.supports_workspace:
            raise UnknownAutomationControlError()
        return self.master_enabled(definition.key) and self.workspace_enabled(
            workspace_id, definition.key
        )

    def master_states(self) -> tuple[AutomationControlState, ...]:
        return tuple(
            AutomationControlState(
                key=definition.key.value,
                label=definition.label,
                description=definition.description,
                master_enabled=self.master_enabled(definition.key),
                workspace_enabled=None,
                effective_enabled=self.master_enabled(definition.key),
                external=definition.external,
            )
            for definition in AUTOMATION_CONTROL_DEFINITIONS
        )

    def workspace_states(self, workspace_id: int) -> tuple[AutomationControlState, ...]:
        states: list[AutomationControlState] = []
        for definition in AUTOMATION_CONTROL_DEFINITIONS:
            if not definition.supports_workspace:
                continue
            master_enabled = self.master_enabled(definition.key)
            workspace_enabled = self.workspace_enabled(workspace_id, definition.key)
            states.append(
                AutomationControlState(
                    key=definition.key.value,
                    label=definition.label,
                    description=definition.description,
                    master_enabled=master_enabled,
                    workspace_enabled=workspace_enabled,
                    effective_enabled=master_enabled and workspace_enabled,
                    external=definition.external,
                )
            )
        return tuple(states)

    def set_master(
        self,
        value: str | AutomationControlKey,
        *,
        enabled: bool,
        actor: str,
    ) -> None:
        definition = control_definition(value)
        row = self.session.get(PlatformAutomationControl, definition.key.value)
        if row is None:
            row = PlatformAutomationControl(
                key=definition.key.value,
                enabled=enabled,
                updated_by=actor,
            )
            self.session.add(row)
        else:
            row.enabled = enabled
            row.updated_by = actor
        self.session.add(
            AutomationControlAudit(
                scope="platform",
                workspace_id=None,
                key=definition.key.value,
                enabled=enabled,
                actor=actor,
            )
        )

    def set_workspace(
        self,
        workspace_id: int,
        value: str | AutomationControlKey,
        *,
        enabled: bool,
        actor: str,
    ) -> None:
        definition = control_definition(value)
        if not definition.supports_workspace:
            raise UnknownAutomationControlError()
        row = self.session.get(
            WorkspaceAutomationControl,
            (workspace_id, definition.key.value),
        )
        if row is None:
            row = WorkspaceAutomationControl(
                workspace_id=workspace_id,
                key=definition.key.value,
                enabled=enabled,
                updated_by=actor,
            )
            self.session.add(row)
        else:
            row.enabled = enabled
            row.updated_by = actor
        self.session.add(
            AutomationControlAudit(
                scope="workspace",
                workspace_id=workspace_id,
                key=definition.key.value,
                enabled=enabled,
                actor=actor,
            )
        )
