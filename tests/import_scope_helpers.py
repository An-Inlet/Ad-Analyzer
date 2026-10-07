from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy.orm import Session


def seed_google_scope(session: Session) -> None:
    if session.get(Workspace, 1) is None:
        session.add(Workspace(id=1, slug="test-brand", name="Test Brand", client_name="Test Brand"))
        session.flush()
    session.add(
        WorkspaceIntegration(
            id=1,
            workspace_id=1,
            integration_key="google-test",
            provider="google_ads",
            display_name="Google",
            status="active",
            configuration={},
            secret_manager_reference="fixture-google-v1",
        )
    )
    session.flush()
    session.add(
        AdvertisingAccount(
            id=1,
            workspace_id=1,
            connection_id=1,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="acct-1",
            name="Provisioned Account",
            currency_code="USD",
        )
    )
    session.commit()
