from enum import StrEnum


class MeasurementContractStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"


class MeasurementSourceOfTruth(StrEnum):
    CRM = "crm"


class PlatformConversionRole(StrEnum):
    DIAGNOSTIC_ONLY = "diagnostic_only"
    DISABLED = "disabled"


class AttributionModel(StrEnum):
    LAST_ELIGIBLE_PAID_TOUCH = "last_eligible_paid_touch"


class CustomerValueMode(StrEnum):
    OBSERVED_REVENUE_ONLY = "observed_revenue_only"
    OBSERVED_PLUS_MODELED_LTV = "observed_plus_modeled_ltv"


class MeasurementStageCategory(StrEnum):
    LEADING_INDICATOR = "leading_indicator"
    OPTIMIZATION_OUTCOME = "optimization_outcome"
    BUSINESS_OUTCOME = "business_outcome"
    VALUE_ADJUSTMENT = "value_adjustment"
    NEGATIVE_OUTCOME = "negative_outcome"


class MeasurementEventSource(StrEnum):
    CRM = "crm"
    WEB_ANALYTICS = "web_analytics"
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"


class MeasurementAuthority(StrEnum):
    AUTHORITATIVE = "authoritative"
    DIAGNOSTIC = "diagnostic"


class MeasurementValueBehavior(StrEnum):
    IGNORE = "ignore"
    SET = "set"
    ADJUST = "adjust"
