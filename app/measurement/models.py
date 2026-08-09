from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.measurement.enums import (
    AttributionModel,
    CustomerValueMode,
    MeasurementAuthority,
    MeasurementContractStatus,
    MeasurementEventSource,
    MeasurementSourceOfTruth,
    MeasurementValueBehavior,
    PlatformConversionRole,
    WebAnalyticsSource,
)
from app.workspaces.models import Workspace  # noqa: F401


def utc_now() -> datetime:
    return datetime.now(UTC)


class MeasurementTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class MeasurementContract(MeasurementTimestampMixin, Base):
    """One explicit business-measurement policy for one client workspace."""

    __tablename__ = "measurement_contracts"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_measurement_contracts_version"),
        CheckConstraint(
            "status IN ('draft', 'active')",
            name="ck_measurement_contracts_status",
        ),
        CheckConstraint(
            "status <> 'active' OR effective_at IS NOT NULL",
            name="ck_measurement_contracts_active_effective",
        ),
        CheckConstraint(
            "currency_code = upper(currency_code) AND length(currency_code) = 3",
            name="ck_measurement_contracts_currency",
        ),
        CheckConstraint(
            "source_of_truth = 'crm'",
            name="ck_measurement_contracts_source_of_truth",
        ),
        CheckConstraint(
            "platform_conversion_role IN ('diagnostic_only', 'disabled')",
            name="ck_measurement_contracts_platform_conversion_role",
        ),
        CheckConstraint(
            "attribution_model = 'last_eligible_paid_touch'",
            name="ck_measurement_contracts_attribution_model",
        ),
        CheckConstraint(
            "customer_value_mode IN ('observed_revenue_only', "
            "'observed_plus_modeled_ltv')",
            name="ck_measurement_contracts_customer_value_mode",
        ),
        CheckConstraint(
            "click_lookback_days BETWEEN 1 AND 365",
            name="ck_measurement_contracts_click_lookback",
        ),
        CheckConstraint(
            "engaged_view_lookback_days BETWEEN 0 AND 30",
            name="ck_measurement_contracts_view_lookback",
        ),
        CheckConstraint(
            "outcome_maturity_days BETWEEN 1 AND 730",
            name="ck_measurement_contracts_outcome_maturity",
        ),
        CheckConstraint(
            "customer_value_horizon_days BETWEEN 1 AND 3650",
            name="ck_measurement_contracts_value_horizon",
        ),
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MeasurementContractStatus.DRAFT.value
    )
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source_of_truth: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MeasurementSourceOfTruth.CRM.value
    )
    platform_conversion_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PlatformConversionRole.DIAGNOSTIC_ONLY.value
    )
    attribution_model: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AttributionModel.LAST_ELIGIBLE_PAID_TOUCH.value
    )
    click_lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    engaged_view_lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome_maturity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    customer_value_mode: Mapped[str] = mapped_column(
        String(64), nullable=False, default=CustomerValueMode.OBSERVED_REVENUE_ONLY.value
    )
    customer_value_horizon_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365
    )
    optimization_goal_stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    business_value_stage_key: Mapped[str] = mapped_column(String(64), nullable=False)


class MeasurementStageDefinition(MeasurementTimestampMixin, Base):
    """A normalized stage used to compare top- and bottom-of-funnel outcomes."""

    __tablename__ = "measurement_stage_definitions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "stage_key",
            name="uq_measurement_stages_workspace_key",
        ),
        CheckConstraint(
            "stage_key = lower(stage_key) AND stage_key NOT LIKE '% %'",
            name="ck_measurement_stages_key_canonical",
        ),
        CheckConstraint("position >= 1", name="ck_measurement_stages_position"),
        CheckConstraint(
            "category IN ('leading_indicator', 'optimization_outcome', "
            "'business_outcome', 'value_adjustment', 'negative_outcome')",
            name="ck_measurement_stages_category",
        ),
        Index(
            "ix_measurement_stages_workspace_position",
            "workspace_id",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_contracts.workspace_id", ondelete="CASCADE"), nullable=False
    )
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    counts_toward_funnel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    accepts_monetary_value: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)


class MeasurementEventMapping(MeasurementTimestampMixin, Base):
    """Maps one source event to one workspace stage with explicit authority."""

    __tablename__ = "measurement_event_mappings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "event_source",
            "source_event_type",
            name="uq_measurement_mappings_workspace_source_event",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "stage_key"],
            [
                "measurement_stage_definitions.workspace_id",
                "measurement_stage_definitions.stage_key",
            ],
            name="fk_measurement_mappings_workspace_stage",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "event_source IN ('crm', 'web_analytics', 'google_ads', 'meta_ads')",
            name="ck_measurement_mappings_event_source",
        ),
        CheckConstraint(
            "authority IN ('authoritative', 'diagnostic')",
            name="ck_measurement_mappings_authority",
        ),
        CheckConstraint(
            "value_behavior IN ('ignore', 'set', 'adjust')",
            name="ck_measurement_mappings_value_behavior",
        ),
        CheckConstraint(
            "source_event_type = lower(source_event_type) "
            "AND source_event_type NOT LIKE '% %'",
            name="ck_measurement_mappings_event_canonical",
        ),
        Index(
            "ix_measurement_mappings_workspace_stage",
            "workspace_id",
            "stage_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_contracts.workspace_id", ondelete="CASCADE"), nullable=False
    )
    event_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MeasurementEventSource.CRM.value
    )
    source_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    authority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MeasurementAuthority.AUTHORITATIVE.value
    )
    value_behavior: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MeasurementValueBehavior.IGNORE.value
    )


class WebAnalyticsEvent(MeasurementTimestampMixin, Base):
    """An allowlisted GA4 event with only pseudonymous correlation identifiers."""

    __tablename__ = "web_analytics_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_system",
            "external_event_id",
            name="uq_web_events_workspace_source_external",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_web_events_account_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            name="fk_web_events_campaign_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ad_group_id", "campaign_id"],
            ["ad_groups.id", "ad_groups.campaign_id"],
            name="fk_web_events_ad_group_campaign",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_system = 'ga4'",
            name="ck_web_events_source_system",
        ),
        CheckConstraint(
            "event_name = lower(event_name) AND event_name NOT LIKE '% %'",
            name="ck_web_events_name_canonical",
        ),
        CheckConstraint(
            "length(event_fingerprint) = 64",
            name="ck_web_events_fingerprint_length",
        ),
        CheckConstraint(
            "length(user_pseudo_id_digest) = 64",
            name="ck_web_events_user_digest_length",
        ),
        CheckConstraint(
            "length(session_id_digest) = 64",
            name="ck_web_events_session_digest_length",
        ),
        CheckConstraint(
            "subject_id_digest IS NULL OR length(subject_id_digest) = 64",
            name="ck_web_events_subject_digest_length",
        ),
        CheckConstraint(
            "(click_id_digest IS NULL AND click_id_kind IS NULL) OR "
            "(length(click_id_digest) = 64 AND click_id_kind IN ('gclid', 'gbraid', 'wbraid'))",
            name="ck_web_events_click_digest_pair",
        ),
        CheckConstraint(
            "campaign_id IS NULL OR account_id IS NOT NULL",
            name="ck_web_events_campaign_requires_account",
        ),
        CheckConstraint(
            "ad_group_id IS NULL OR campaign_id IS NOT NULL",
            name="ck_web_events_ad_group_requires_campaign",
        ),
        CheckConstraint(
            "NOT is_paid_touchpoint OR "
            "(account_id IS NOT NULL AND campaign_id IS NOT NULL)",
            name="ck_web_events_paid_touchpoint_campaign",
        ),
        CheckConstraint(
            "country_code IS NULL OR "
            "(country_code = upper(country_code) AND length(country_code) = 2)",
            name="ck_web_events_country_code",
        ),
        Index(
            "ix_web_events_workspace_occurred",
            "workspace_id",
            "occurred_at",
        ),
        Index(
            "ix_web_events_workspace_subject_occurred",
            "workspace_id",
            "subject_id_digest",
            "occurred_at",
        ),
        Index(
            "ix_web_events_workspace_click_occurred",
            "workspace_id",
            "click_id_digest",
            "occurred_at",
        ),
        Index(
            "ix_web_events_workspace_campaign_occurred",
            "workspace_id",
            "campaign_id",
            "occurred_at",
        ),
        Index(
            "ix_web_events_workspace_ad_group_occurred",
            "workspace_id",
            "ad_group_id",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WebAnalyticsSource.GA4.value
    )
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_pseudo_id_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id_digest: Mapped[str | None] = mapped_column(String(64))
    session_id_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    click_id_kind: Mapped[str | None] = mapped_column(String(16))
    click_id_digest: Mapped[str | None] = mapped_column(String(64))
    account_id: Mapped[int | None] = mapped_column(Integer)
    campaign_id: Mapped[int | None] = mapped_column(Integer)
    ad_group_id: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(64))
    medium: Mapped[str | None] = mapped_column(String(64))
    device_category: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    country_code: Mapped[str | None] = mapped_column(String(2))
    region_code: Mapped[str | None] = mapped_column(String(64))
    landing_page_path: Mapped[str | None] = mapped_column(String(1024))
    is_paid_touchpoint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
