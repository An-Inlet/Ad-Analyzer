"""Pure browser composition and private media bounds use no provider access."""

import subprocess

from tests.test_customer_portal import portal_executable


def test_campaign_creation_browser_contracts() -> None:
    node = portal_executable("node")
    subprocess.run([node, "tests/javascript/campaign_create_test.mjs"], check=True, timeout=20)
