"""OAuth callback query strings must never enter application access logs."""

import logging


class OAuthAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(
            path in message for path in ("/dashboard/shopify/callback", "/dashboard/meta/callback")
        )


def install_access_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, OAuthAccessFilter) for f in logger.filters):
        logger.addFilter(OAuthAccessFilter())
