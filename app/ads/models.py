from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.ads.enums import (
    AdvertisingPlatform,
    ExecutionStatus,
    JobRunStatus,
    MetricEntityType,
    RecommendationStatus,
)
from app.database.session import Base
from app.workspaces.models import Workspace  # noqa: F401


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


platform_enum = Enum(
    AdvertisingPlatform,
    name="advertising_platform",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)
job_status_enum = Enum(
    JobRunStatus,
    name="job_run_status",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)
recommendation_status_enum = Enum(
    RecommendationStatus,
    name="recommendation_status",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)
execution_status_enum = Enum(
    ExecutionStatus,
    name="execution_status",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class AdvertisingAccount(TimestampMixin, Base):
    __tablename__ = "advertising_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            name="fk_account_connection_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", "connection_id", name="uq_account_connection_scope"),
        UniqueConstraint(
            "workspace_id",
            "platform",
            "external_account_id",
            name="uq_ad_accounts_workspace_platform_external",
        ),
        UniqueConstraint("id", "platform", name="uq_ad_accounts_id_platform"),
        UniqueConstraint("id", "workspace_id", name="uq_ad_accounts_id_workspace"),
        Index("ix_ad_accounts_workspace_platform", "workspace_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(Integer)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    time_zone: Mapped[str | None] = mapped_column(String(64))

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    job_runs: Mapped[list["JobRun"]] = relationship(
        back_populates="account",
        passive_deletes=True,
        primaryjoin=(
            "and_(AdvertisingAccount.id == JobRun.account_id, "
            "AdvertisingAccount.platform == JobRun.platform, "
            "AdvertisingAccount.workspace_id == JobRun.workspace_id)"
        ),
        foreign_keys="[JobRun.account_id, JobRun.platform, JobRun.workspace_id]",
    )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "platform",
            "external_campaign_id",
            name="uq_campaigns_account_platform_external",
        ),
        UniqueConstraint("id", "platform", name="uq_campaigns_id_platform"),
        UniqueConstraint("id", "account_id", name="uq_campaigns_id_account"),
        ForeignKeyConstraint(
            ["account_id", "platform"],
            ["advertising_accounts.id", "advertising_accounts.platform"],
            name="fk_campaigns_account_platform",
            ondelete="CASCADE",
        ),
        Index("ix_campaigns_account_platform", "account_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_campaign_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64))
    channel_type: Mapped[str | None] = mapped_column(String(64))

    account: Mapped[AdvertisingAccount] = relationship(back_populates="campaigns")
    ad_groups: Mapped[list["AdGroup"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    ad_sets: Mapped[list["AdSet"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    daily_metrics: Mapped[list["DailyMetric"]] = relationship(back_populates="campaign")
    conversion_events: Mapped[list["ConversionEvent"]] = relationship(back_populates="campaign")


class AdGroup(TimestampMixin, Base):
    __tablename__ = "ad_groups"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "platform",
            "external_ad_group_id",
            name="uq_ad_groups_campaign_platform_external",
        ),
        UniqueConstraint("id", "platform", name="uq_ad_groups_id_platform"),
        UniqueConstraint("id", "campaign_id", name="uq_ad_groups_id_campaign"),
        UniqueConstraint(
            "id",
            "campaign_id",
            "platform",
            name="uq_ad_groups_id_campaign_platform",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_ad_groups_campaign_platform",
            ondelete="CASCADE",
        ),
        Index("ix_ad_groups_campaign_platform", "campaign_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_ad_group_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64))

    campaign: Mapped[Campaign] = relationship(back_populates="ad_groups")
    ads: Mapped[list["Ad"]] = relationship(back_populates="ad_group", overlaps="ad_set,ads")
    keywords: Mapped[list["Keyword"]] = relationship(back_populates="ad_group")
    search_terms: Mapped[list["SearchTerm"]] = relationship(back_populates="ad_group")


class AdSet(TimestampMixin, Base):
    __tablename__ = "ad_sets"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "platform",
            "external_ad_set_id",
            name="uq_ad_sets_campaign_platform_external",
        ),
        UniqueConstraint("id", "platform", name="uq_ad_sets_id_platform"),
        UniqueConstraint("id", "campaign_id", "platform", name="uq_ad_sets_id_campaign_platform"),
        ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_ad_sets_campaign_platform",
            ondelete="CASCADE",
        ),
        Index("ix_ad_sets_campaign_platform", "campaign_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_ad_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64))

    campaign: Mapped[Campaign] = relationship(back_populates="ad_sets")
    ads: Mapped[list["Ad"]] = relationship(back_populates="ad_set", overlaps="ad_group,ads")


class Ad(TimestampMixin, Base):
    __tablename__ = "ads"
    __table_args__ = (
        UniqueConstraint("id", "ad_group_id", "platform", name="uq_ads_id_group_platform"),
        UniqueConstraint("id", "ad_set_id", "platform", name="uq_ads_id_set_platform"),
        UniqueConstraint(
            "ad_group_id",
            "platform",
            "external_ad_id",
            name="uq_ads_ad_group_platform_external",
        ),
        UniqueConstraint(
            "ad_set_id",
            "platform",
            "external_ad_id",
            name="uq_ads_ad_set_platform_external",
        ),
        CheckConstraint(
            "(ad_group_id IS NOT NULL AND ad_set_id IS NULL) OR "
            "(ad_group_id IS NULL AND ad_set_id IS NOT NULL)",
            name="ck_ads_exactly_one_parent",
        ),
        ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_ads_ad_group_platform",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ad_set_id", "platform"],
            ["ad_sets.id", "ad_sets.platform"],
            name="fk_ads_ad_set_platform",
            ondelete="CASCADE",
        ),
        Index("ix_ads_platform", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_ad_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64))
    creative_external_id: Mapped[str | None] = mapped_column(String(128))
    creative_name: Mapped[str | None] = mapped_column(String(255))
    ad_group_id: Mapped[int | None] = mapped_column(Integer)
    ad_set_id: Mapped[int | None] = mapped_column(Integer)

    ad_group: Mapped[AdGroup | None] = relationship(back_populates="ads", overlaps="ad_set,ads")
    ad_set: Mapped[AdSet | None] = relationship(back_populates="ads", overlaps="ad_group,ads")


class Keyword(TimestampMixin, Base):
    __tablename__ = "keywords"
    __table_args__ = (
        UniqueConstraint(
            "ad_group_id",
            "platform",
            "external_keyword_id",
            name="uq_keywords_ad_group_platform_external",
        ),
        UniqueConstraint(
            "id",
            "ad_group_id",
            "platform",
            name="uq_keywords_id_ad_group_platform",
        ),
        ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_keywords_ad_group_platform",
            ondelete="CASCADE",
        ),
        Index("ix_keywords_ad_group_platform", "ad_group_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_keyword_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(String(512), nullable=False)
    match_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(64))

    ad_group: Mapped[AdGroup] = relationship(back_populates="keywords")


class SearchTerm(TimestampMixin, Base):
    __tablename__ = "search_terms"
    __table_args__ = (
        UniqueConstraint(
            "ad_group_id", "platform", "term", name="uq_search_terms_ad_group_platform_term"
        ),
        UniqueConstraint(
            "id",
            "ad_group_id",
            "platform",
            name="uq_search_terms_id_ad_group_platform",
        ),
        ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_search_terms_ad_group_platform",
            ondelete="CASCADE",
        ),
        Index("ix_search_terms_ad_group_platform", "ad_group_id", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    term: Mapped[str] = mapped_column(String(512), nullable=False)
    match_type: Mapped[str | None] = mapped_column(String(64))

    ad_group: Mapped[AdGroup] = relationship(back_populates="search_terms")


class DailyMetric(TimestampMixin, Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "metric_date",
            "entity_type",
            "entity_id",
            name="uq_daily_metrics_platform_date_entity",
        ),
        Index("ix_daily_metrics_platform_date", "platform", "metric_date"),
        Index(
            "ix_daily_metrics_entity_type_entity_date",
            "entity_type",
            "entity_id",
            "metric_date",
        ),
        CheckConstraint("cost_micros >= 0", name="ck_daily_metrics_cost_nonnegative"),
        CheckConstraint(
            "((entity_type = 'campaign' AND entity_id = campaign_id "
            "AND ad_group_id IS NULL AND keyword_id IS NULL AND search_term_id IS NULL) OR "
            "(entity_type = 'ad_group' AND entity_id = ad_group_id "
            "AND ad_group_id IS NOT NULL AND keyword_id IS NULL AND search_term_id IS NULL) OR "
            "(entity_type = 'keyword' AND entity_id = keyword_id "
            "AND ad_group_id IS NOT NULL AND keyword_id IS NOT NULL "
            "AND search_term_id IS NULL) OR "
            "(entity_type = 'search_term' AND entity_id = search_term_id "
            "AND ad_group_id IS NOT NULL AND keyword_id IS NULL "
            "AND search_term_id IS NOT NULL)) "
            "AND ad_set_id IS NULL AND ad_id IS NULL OR "
            "(entity_type = 'ad_set' AND entity_id = ad_set_id AND ad_set_id IS NOT NULL "
            "AND ad_id IS NULL AND ad_group_id IS NULL AND keyword_id IS NULL "
            "AND search_term_id IS NULL) OR "
            "(entity_type = 'ad' AND entity_id = ad_id AND ad_id IS NOT NULL "
            "AND keyword_id IS NULL AND search_term_id IS NULL "
            "AND ((ad_set_id IS NOT NULL AND ad_group_id IS NULL) OR "
            "(ad_set_id IS NULL AND ad_group_id IS NOT NULL)))",
            name="ck_daily_metrics_entity_scope",
        ),
        ForeignKeyConstraint(
            ["ad_set_id", "campaign_id", "platform"],
            ["ad_sets.id", "ad_sets.campaign_id", "ad_sets.platform"],
            name="fk_metric_ad_set",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ad_id", "ad_set_id", "platform"],
            ["ads.id", "ads.ad_set_id", "ads.platform"],
            name="fk_metric_ad_set_ad",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ad_id", "ad_group_id", "platform"],
            ["ads.id", "ads.ad_group_id", "ads.platform"],
            name="fk_metric_ad_group_ad",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_daily_metrics_campaign_platform",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ad_group_id", "campaign_id", "platform"],
            ["ad_groups.id", "ad_groups.campaign_id", "ad_groups.platform"],
            name="fk_daily_metrics_ad_group_campaign_platform",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["keyword_id", "ad_group_id", "platform"],
            ["keywords.id", "keywords.ad_group_id", "keywords.platform"],
            name="fk_daily_metrics_keyword_ad_group_platform",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["search_term_id", "ad_group_id", "platform"],
            ["search_terms.id", "search_terms.ad_group_id", "search_terms.platform"],
            name="fk_daily_metrics_search_term_ad_group_platform",
            ondelete="CASCADE",
        ),
        Index(
            "ix_daily_metrics_ad_group_date",
            "ad_group_id",
            "metric_date",
        ),
        Index(
            "ix_daily_metrics_keyword_date",
            "keyword_id",
            "metric_date",
        ),
        Index(
            "ix_daily_metrics_search_term_date",
            "search_term_id",
            "metric_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=MetricEntityType.CAMPAIGN.value
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ad_set_id: Mapped[int | None] = mapped_column(Integer)
    ad_id: Mapped[int | None] = mapped_column(Integer)
    ad_group_id: Mapped[int | None] = mapped_column(Integer)
    keyword_id: Mapped[int | None] = mapped_column(Integer)
    search_term_id: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    conversions: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0"), nullable=False
    )
    conversion_value_micros: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    campaign: Mapped[Campaign | None] = relationship(back_populates="daily_metrics")


class ConversionEvent(TimestampMixin, Base):
    __tablename__ = "conversion_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "platform",
            "external_conversion_id",
            name="uq_conversion_events_workspace_platform_external",
        ),
        Index(
            "ix_conversion_events_workspace_platform_occurred",
            "workspace_id",
            "platform",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    external_conversion_id: Mapped[str] = mapped_column(String(128), nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_micros: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency_code: Mapped[str | None] = mapped_column(String(3))

    campaign: Mapped[Campaign | None] = relationship(back_populates="conversion_events")


class JobRun(TimestampMixin, Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            name="fk_job_connection_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "connection_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            name="fk_job_account_connection",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_job_runs_id_workspace"),
        ForeignKeyConstraint(
            ["account_id", "platform"],
            ["advertising_accounts.id", "advertising_accounts.platform"],
            name="fk_job_runs_account_platform",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_job_runs_account_workspace",
            ondelete="RESTRICT",
        ),
        Index("ix_job_runs_platform_started", "platform", "started_at"),
        Index("ix_job_runs_workspace_started", "workspace_id", desc("started_at")),
        Index(
            "ix_job_runs_account_platform_started_id",
            "account_id",
            "platform",
            desc("started_at"),
            desc("id"),
            postgresql_where=text("account_id IS NOT NULL"),
        ),
        Index(
            "ix_job_runs_account_platform_status_finished",
            "account_id",
            "platform",
            "status",
            desc("finished_at"),
            postgresql_where=text("account_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(Integer)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    account_id: Mapped[int | None] = mapped_column(Integer)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[JobRunStatus] = mapped_column(
        job_status_enum, default=JobRunStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    account: Mapped[AdvertisingAccount | None] = relationship(
        back_populates="job_runs",
        primaryjoin=(
            "and_(AdvertisingAccount.id == JobRun.account_id, "
            "AdvertisingAccount.platform == JobRun.platform, "
            "AdvertisingAccount.workspace_id == JobRun.workspace_id)"
        ),
        foreign_keys="[JobRun.account_id, JobRun.platform, JobRun.workspace_id]",
    )


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index(
            "ix_recommendations_workspace_account_status",
            "workspace_id",
            "account_id",
            "status",
        ),
        Index(
            "ix_recommendations_workspace_deduplication",
            "workspace_id",
            "deduplication_key",
        ),
        Index(
            "uq_recommendations_active_deduplication",
            "workspace_id",
            "deduplication_key",
            unique=True,
            postgresql_where=text(
                "deduplication_key IS NOT NULL AND status IN "
                "('pending_review', 'approved', 'executed_dry_run')"
            ),
            sqlite_where=text(
                "deduplication_key IS NOT NULL AND status IN "
                "('pending_review', 'approved', 'executed_dry_run')"
            ),
        ),
        Index(
            "ix_recommendations_source_analysis_run",
            "source_analysis_run_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_recommendations_workspace",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            name="fk_recommendations_campaign_account",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["account_id", "platform"],
            ["advertising_accounts.id", "advertising_accounts.platform"],
            name="fk_recommendations_account_platform",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_recommendations_account_workspace",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    platform: Mapped[AdvertisingPlatform] = mapped_column(platform_enum, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(Integer)
    source_analysis_run_id: Mapped[int | None] = mapped_column(Integer)
    deduplication_key: Mapped[str | None] = mapped_column(String(64))
    recommendation_type: Mapped[str] = mapped_column(String(96), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_metrics: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    planned_action: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        recommendation_status_enum, default=RecommendationStatus.PENDING_REVIEW, nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationAudit(TimestampMixin, Base):
    __tablename__ = "recommendation_audits"
    __table_args__ = (
        Index("ix_recommendation_audits_recommendation", "recommendation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class ExecutionAudit(TimestampMixin, Base):
    __tablename__ = "execution_audits"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "idempotency_key",
            name="uq_execution_audits_recommendation_idempotency_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(execution_status_enum, nullable=False)
    dry_run: Mapped[bool] = mapped_column(default=True, nullable=False)
    validation_errors: Mapped[list[object]] = mapped_column(JSON, default=list, nullable=False)
    rollback_instructions: Mapped[str] = mapped_column(Text, nullable=False)
