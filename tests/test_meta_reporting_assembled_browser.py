# ruff: noqa: E501
"""Actual app/static/controllers/API/SQL over local TLS; provider wire alone is mocked."""

import json
import socket
import subprocess
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pytest
import uvicorn
from app.planning_documents.documents import PlanVersion
from app.settings import settings

from tests.browser_targets import wait_for_page_target
from tests.meta_reporting_assembly_fixture import Assembly
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_portal import portal_executable
from tests.test_meta_customer_flow import configuration as configuration
from tests.test_meta_customer_flow import customer_engine as customer_engine
from tests.test_meta_customer_flow import meta as meta
from tests.test_meta_customer_flow import replicas as replicas
from tests.test_shopify_consent_browser import Browser


@pytest.mark.parametrize("value", ["10", "0", None])
def test_actual_meta_reporting_to_plan(
    meta: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None
) -> None:
    f = meta
    f.value = value
    a = Assembly(f, monkeypatch)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            a.app,
            lifespan="off",
            log_level="critical",
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    profile = tmp_path / "browser"
    process = subprocess.Popen(
        [
            portal_executable(
                "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
            ),
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--ignore-certificate-errors",
            "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    browser: Browser | None = None
    try:
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not active.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        port = active.read_text().splitlines()[0]

        def tabs() -> list[dict[str, Any]]:
            with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                return list(json.load(response))

        browser = Browser(wait_for_page_target(tabs), origin)
        b = browser
        b.call("Page.navigate", {"url": origin + "/app/reporting"})
        b.wait("document.querySelector('#report-refresh')!==null")
        assert (
            b.evaluate(
                "fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-owner:browser'})}).then(r=>r.status)"
            )
            == 200
        )
        b.evaluate("document.getElementById('report-refresh').click()")
        b.wait("document.getElementById('report-workspace').options.length===2")

        def change(prefix: str, field: str, chosen: str) -> None:
            b.evaluate(
                f"(()=>{{const n=document.getElementById({json.dumps(prefix + '-' + field)});n.value={json.dumps(chosen)};n.dispatchEvent(new Event('change'));}})()"
            )

        change("report", "workspace", str(f.wid))
        b.wait(
            "document.getElementById('report-account').options.length===2 && !document.getElementById('report-account').disabled"
        )
        change("report", "account", str(f.aid))
        b.wait("!document.getElementById('report-range').disabled")
        monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)
        b.evaluate(
            "document.getElementById('report-start').value='2026-08-01';document.getElementById('report-end').value='2026-09-30';document.getElementById('report-form').requestSubmit()"
        )
        b.wait("document.getElementById('report-message').textContent.includes('not configured')")
        assert not a.constructed
        monkeypatch.setattr(settings, "customer_meta_reporting_enabled", True)
        b.wait("!document.getElementById('report-range').disabled")
        b.evaluate("document.getElementById('report-form').requestSubmit()")
        b.wait(
            "!document.getElementById('report-range-result').hidden && !document.getElementById('report-discover').disabled"
        )
        b.evaluate("document.getElementById('report-discover').click()")
        b.wait(
            "document.getElementById('report-option').options.length===2 && !document.getElementById('report-option').disabled"
        )
        assert b.evaluate("document.getElementById('report-option').value") == ""
        option = b.evaluate("document.getElementById('report-option').options[1].value")
        change("report", "option", option)
        b.evaluate("document.getElementById('report-confirm').click()")
        b.wait(
            "!document.getElementById('report-capture').hidden && !document.getElementById('report-capture').disabled"
        )
        b.evaluate("document.getElementById('report-capture').click()")
        b.wait(
            "!document.getElementById('report-capture-result').hidden && !document.getElementById('report-use-capture').disabled"
        )
        capture = b.evaluate(
            "document.getElementById('report-capture-details').children[1].textContent"
        )
        assert b.evaluate(
            "document.getElementById('report-capture-details').textContent.includes('Unknown')"
        )
        assert len(a.constructed) == len(a.closed) == 1 and len(f.calls) == 2
        b.evaluate("document.getElementById('report-use-capture').click()")
        b.wait(
            "location.pathname==='/app/planning' && document.getElementById('planning-workspace')?.options.length===2"
        )
        change("planning", "workspace", str(f.wid))
        b.wait(
            "!document.getElementById('planning-new').disabled && !document.getElementById('planning-new').hidden"
        )
        b.evaluate("document.getElementById('planning-new').click()")
        b.wait(
            "!document.getElementById('planning-editor').hidden && !document.getElementById('planning-goal').disabled"
        )
        change("planning", "goal", f.basis.goal_id)
        b.evaluate(
            f"(()=>{{const n=document.querySelector('#planning-accounts input[value=\"{f.aid}\"]');n.checked=true;n.dispatchEvent(new Event('change'));}})()"
        )
        assert b.evaluate("document.querySelector('[data-capture-account]').value") == ""
        b.evaluate("document.getElementById('planning-apply-capture').click()")
        b.wait(
            "document.getElementById('planning-capture-handoff').hidden && !document.getElementById('planning-save').disabled"
        )
        assert b.evaluate("document.querySelector('[data-capture-account]').value") == capture
        b.evaluate(
            "document.getElementById('planning-milestone').value='Reach the confirmed sales goal';document.getElementById('planning-start').value='2026-09-01T04:00';document.getElementById('planning-end').value='2026-10-01T04:00';document.getElementById('planning-form').requestSubmit()"
        )
        b.wait(
            "!document.getElementById('planning-generate').hidden && !document.getElementById('planning-generate').disabled"
        )
        b.evaluate("document.getElementById('planning-generate').click()")
        b.wait(
            "!document.getElementById('planning-document').hidden && !document.getElementById('planning-export').disabled"
        )
        root = f"/api/customer/v1/workspaces/{f.wid}/planning/plans"
        # Read actual server receipts in the same browser/session, not constructed DTOs.
        pages = b.evaluate(f"fetch({json.dumps(root)}).then(r=>r.json())")
        pid = pages["items"][0]["plan_id"]
        result = {}
        for label, suffix in [
            ("current", ""),
            ("history", "/versions/1"),
            ("export", "/export?version=1"),
        ]:
            result[label] = b.evaluate(
                f"fetch({json.dumps(root + '/' + pid + suffix)}).then(r=>r.json())"
            )
        documents = [PlanVersion.model_validate(v["document"]) for v in result.values()]
        assert len({d.digest() for d in documents}) == 1
        doc = documents[0]
        assert doc.selected_reporting_proof is not None
        pin = doc.selected_reporting_proof.accounts[0].capture_pin
        assert pin and pin.capture_id == capture and pin.observation_provenance
        assert pin.observation_provenance.attribution.report_time_basis == "unknown"
        assert (
            pin.observation_provenance.settings
            and pin.observation_provenance.settings.value_unit == "unknown"
        )
        assert f"selected count {value if value is not None else 'unavailable'} (" in " ".join(
            x.rationale for x in doc.actions
        )
        assert doc.advertising_writes_enabled is False and doc.spending_authority == "none"
        (tmp_path / "assembled-meta-plan.json").write_text(json.dumps(result, indent=2))
    except BaseException:
        if browser is not None:
            with suppress(Exception):
                (tmp_path / "browser-failure.json").write_text(
                    json.dumps(
                        browser.evaluate("({url:location.href,body:document.body.innerText})"),
                        indent=2,
                    )
                )
        raise
    finally:
        if browser is not None:
            browser.context.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
