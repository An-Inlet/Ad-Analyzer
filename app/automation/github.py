import json
from http.client import HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import SecretStr

GITHUB_HOURLY_AUDIT_VARIABLE = "PRODUCTION_OPERATIONS_AUDIT_ENABLED"


class GitHubAutomationControlError(RuntimeError):
    """Sanitized external-control failure."""

    def __init__(self) -> None:
        super().__init__("GitHub automation control is temporarily unavailable.")


class GitHubActionsVariableClient:
    def __init__(self, *, token: SecretStr, repository: str) -> None:
        owner, name = repository.split("/", 1)
        self.repository_path = f"{quote(owner, safe='')}/{quote(name, safe='')}"
        self.token = token

    def set_hourly_production_audit_enabled(self, enabled: bool) -> None:
        value = "true" if enabled else "false"
        variable_path = quote(GITHUB_HOURLY_AUDIT_VARIABLE, safe="")
        item_url = (
            f"https://api.github.com/repos/{self.repository_path}/actions/variables/{variable_path}"
        )
        payload = {"name": GITHUB_HOURLY_AUDIT_VARIABLE, "value": value}
        status = self._request("PATCH", item_url, payload, allow_not_found=True)
        if status == 404:
            collection_url = (
                f"https://api.github.com/repos/{self.repository_path}/actions/variables"
            )
            self._request("POST", collection_url, payload)

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, str],
        *,
        allow_not_found: bool = False,
    ) -> int:
        request = Request(
            url,
            method=method,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": "ad-analyzer-automation-controls",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return self._status(response)
        except HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return 404
            raise GitHubAutomationControlError() from None
        except (TimeoutError, URLError):
            raise GitHubAutomationControlError() from None

    @staticmethod
    def _status(response: HTTPResponse) -> int:
        status = response.getcode()
        if not isinstance(status, int) or status not in {201, 204}:
            raise GitHubAutomationControlError()
        return status
