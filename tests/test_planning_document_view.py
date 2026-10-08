"""Real Chromium DOM test of display-only documents; not an authenticated API journey."""

import functools
import json
import os
import shutil
import signal
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.test_customer_portal import portal_executable
from tests.test_planning_composer import compose, fixture


def test_document_view_escapes_text_labels_history_and_clears_foreign_response(
    tmp_path: Path,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    inputs, bundle, policy = fixture(
        product_offer='<img src=x onerror="window.injected=true">', maximum_creative_assets=1
    )
    plan = compose(inputs, bundle, policy)
    (tmp_path / "plan.json").write_text(plan.model_dump_json())
    shutil.copy("app/portal/static/plan-document.mjs", tmp_path / "plan-document.mjs")
    (tmp_path / "index.html").write_text(
        '<!doctype html><main id="host"></main><output id="result">RUNNING</output>'
        '<script type="module" src="/test.mjs"></script>'
    )
    (tmp_path / "test.mjs").write_text(
        """
import {renderPlanDocument,clearPlanDocument} from '/plan-document.mjs';
const assert=(ok,message)=>{if(!ok)throw new Error(message);};
try {
 const plan=await (await fetch('/plan.json')).json(),host=document.querySelector('#host');
 const options={workspaceId:plan.inputs.workspace_id,
                planId:plan.inputs.plan_id,freshness:'current'};
 const result=renderPlanDocument(host,plan,options,Date.parse(plan.generated_at));
 assert(result.freshness==='current','current status');
 assert(host.textContent.includes('Independent Budget Alternatives'),'alternatives');
 assert(host.textContent.includes('No matching campaign performance'),'specific rationale');
 assert(host.textContent.includes(plan.inputs.product_offer),'literal product facts');
 assert(!host.querySelector('img,script,a,button,input')&&!window.injected,'unsafe DOM/control');
 assert(host.textContent.includes('not been expert-qualified'),'quality limitation');
 assert(host.textContent.includes('UTC'),'timezone');
 const stale=renderPlanDocument(host,plan,options,Date.parse(plan.valid_until));
 assert(stale.freshness==='expired'&&host.textContent.includes('Expired Evidence'),'expiry');
 renderPlanDocument(host,plan,{...options,freshness:'source_changed'},Date.parse(plan.generated_at));
 assert(host.textContent.includes('Source Changed'),'historical source status');
 try {renderPlanDocument(host,plan,{...options,workspaceId:999999});
      throw new Error('accepted foreign');}
 catch(error){assert(error.message!=='accepted foreign','foreign rejected');}
 assert(host.hidden&&!host.childNodes.length,'foreign response cleared');
 renderPlanDocument(host,plan,options,Date.parse(plan.generated_at));clearPlanDocument(host);
 assert(host.hidden&&!host.childNodes.length,'session clear');
 document.querySelector('#result').textContent='PASS';
} catch(error) {document.querySelector('#result').textContent='FAIL '+error.stack;}
await fetch('/result',{method:'POST',body:document.querySelector('#result').textContent});
"""
    )
    complete = threading.Event()
    reports: list[str] = []

    class Handler(SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            length = min(int(self.headers.get("Content-Length", "0")), 10000)
            reports.append(self.rfile.read(length).decode())
            self.send_response(200)
            self.end_headers()
            complete.set()

    handler = functools.partial(Handler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    browser = subprocess.Popen(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={tmp_path / 'browser'}",
            f"http://127.0.0.1:{server.server_port}/index.html",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        assert complete.wait(15), "Browser did not report a document result"
        assert reports == ["PASS"], reports
    finally:
        os.killpg(browser.pid, signal.SIGTERM)
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(browser.pid, signal.SIGKILL)
            browser.wait(timeout=5)
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    assert json.loads((tmp_path / "plan.json").read_text())["version"] == 1
