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

from app.planning_documents.common import fingerprint
from app.planning_documents.comparison import compare_versions
from app.planning_documents.events import CustomerDecision, ManualAssertion
from app.planning_documents.field_comparison import FieldSnapshotV1, compare_fields
from app.planning_documents.responses import EventPage, EventResult

from tests.test_customer_portal import portal_executable
from tests.test_planning_composer import compose, fixture
from tests.test_planning_field_comparison import admission, document, snapshot_data


def test_document_view_escapes_text_labels_history_and_clears_foreign_response(
    tmp_path: Path,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    inputs, bundle, policy = fixture(
        product_offer='<img src=x onerror="window.injected=true">', maximum_creative_assets=1
    )
    plan = compose(inputs, bundle, policy)
    (tmp_path / "plan.json").write_text(plan.model_dump_json())
    binding = dict(
        workspace_id=plan.inputs.workspace_id,
        plan_id=plan.inputs.plan_id,
        version=plan.version,
        document_digest=plan.digest(),
        action_key=plan.actions[0].key,
        action_digest=plan.actions[0].digest(),
        actor_id=plan.inputs.created_by,
        recorded_at=plan.generated_at,
    )
    decision = CustomerDecision(
        **binding,
        event_id="a" * 32,
        supersedes_event_id=None,
        decision="accepted_for_manual_application",
        reason="Reviewed <img src=x>",
    )
    assertion = ManualAssertion(
        **binding,
        event_id="b" * 32,
        supersedes_event_id=None,
        assertion="customer_reports_applied",
        reported_applied_at=plan.generated_at,
        statement="Customer account <script>window.injected=true</script>",
    )
    retraction = ManualAssertion(
        **binding,
        event_id="c" * 32,
        supersedes_event_id=assertion.event_id,
        assertion="retracted",
        reported_applied_at=None,
        statement="Corrected customer report",
    )
    page = EventPage(
        items=tuple(
            EventResult(event_sequence=i, event=e)
            for i, e in enumerate((decision, assertion, retraction), start=1)
        ),
        next_cursor="more-history",
    )
    (tmp_path / "events.json").write_text(page.model_dump_json())
    observed_document = document()
    context = admission(observed_document)
    matching = compare_fields(
        observed_document,
        context,
        FieldSnapshotV1.model_validate(snapshot_data(observed_document)),
    )
    conflicting = compare_fields(
        observed_document,
        context.model_copy(update=dict(event_id="d" * 32)),
        FieldSnapshotV1.model_validate(
            snapshot_data(observed_document, [dict(field="delivery_status", value="enabled")])
        ),
    )
    missing = compare_fields(
        observed_document, context.model_copy(update=dict(event_id="f" * 32)), None
    )
    customer_reports = tuple(
        type(e).model_validate(
            {
                **e.model_dump(mode="python"),
                **context.binding.model_dump(mode="python"),
            }
        )
        for e in (decision, assertion, retraction)
    )
    mixed = EventPage(
        items=tuple(
            EventResult(event_sequence=i, event=e)
            for i, e in enumerate((*customer_reports, matching, conflicting, missing), start=1)
        ),
        next_cursor=None,
    )
    (tmp_path / "observations.json").write_text(mixed.model_dump_json())
    values = []
    for field in ("landing_page", "country_targets"):
        field_document = document(field)
        values.append(
            compare_fields(
                field_document,
                admission(field_document),
                FieldSnapshotV1.model_validate(snapshot_data(field_document)),
            ).model_dump(mode="json")
        )
    (tmp_path / "observation-values.json").write_text(json.dumps(values))
    shutil.copy("app/portal/static/plan-events.mjs", tmp_path / "plan-events.mjs")
    shutil.copy("app/portal/static/plan-observations.mjs", tmp_path / "plan-observations.mjs")
    changed_goal = inputs.goal.model_dump(mode="python")
    changed_definition = inputs.goal.definition.model_copy(update=dict(target_micros=12000000000))
    changed_goal.update(
        definition=changed_definition,
        definition_digest=fingerprint(
            "goal-definition", changed_definition.model_dump(mode="json")
        ),
    )
    revised_inputs, revised_bundle, revised_policy = fixture(goal=changed_goal)
    revised_plan = compose(revised_inputs, revised_bundle, revised_policy)
    (tmp_path / "changed-plan.json").write_text(revised_plan.model_dump_json())
    successor = plan.model_copy(
        update=dict(
            version=2, parent_digest=plan.digest(), summary="<script>window.injected=true</script>"
        )
    )
    comparison = compare_versions(plan, successor)
    (tmp_path / "comparison.json").write_text(comparison.model_dump_json())
    shutil.copy("app/portal/static/plan-comparison.mjs", tmp_path / "plan-comparison.mjs")
    for module in (
        "plan-document.mjs",
        "plan-reporting-comparability.mjs",
        "plan-creative-basis.mjs",
        "plan-google-owner-inputs.mjs",
        "plan-google-owner-review.mjs",
        "plan-owner-campaign-label.mjs",
        "plan-target-picker.mjs",
        "native-targets.mjs",
        "plan-creative-inputs.mjs",
        "plan-capability.mjs",
    ):
        shutil.copy(Path("app/portal/static") / module, tmp_path / module)
    (tmp_path / "index.html").write_text(
        '<!doctype html><main id="host"></main><output id="result">RUNNING</output>'
        '<script type="module" src="/test.mjs"></script>'
    )
    (tmp_path / "test.mjs").write_text(
        """
import {renderPlanDocument,clearPlanDocument} from '/plan-document.mjs';
import {renderPlanComparison} from '/plan-comparison.mjs';
import {renderPlanEvents,clearPlanEvents} from '/plan-events.mjs';
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
 assert(host.textContent.includes('Confirmed Goal Revision 1'),'confirmed goal revision');
 assert(host.textContent.includes('USD 0.001000 Shopify Merchandise Net Sales'),'confirmed target');
 assert(host.textContent.includes('Deadline 2026-10-31'),'deadline');
 assert(host.textContent.includes('Baseline window:'),'baseline window');
 const changed=await (await fetch('/changed-plan.json')).json();
 renderPlanDocument(host,changed,options,Date.parse(changed.generated_at));
 assert(host.textContent.includes('USD 12000.000000 Shopify Merchandise Net Sales'),
        'edited confirmed target distinct from freeform milestone');
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
 const comparison=await (await fetch('/comparison.json')).json();
 const expected={previous_version:comparison.previous_version,
                 current_version:comparison.current_version,
                 previous_digest:comparison.previous_digest,current_digest:comparison.current_digest};
 renderPlanComparison(host,comparison,expected);
 assert(host.textContent.includes('<script>window.injected=true</script>'),'literal diff text');
 assert(!host.querySelector('script')&&!window.injected,'comparison injection');
 assert(host.textContent.includes('not carried forward'),'decision independence');
 renderPlanComparison(host,{...comparison,omitted_changes:17},expected);
 assert(host.textContent.includes('17 additional changes'),'omitted count visible');
 try {renderPlanComparison(host,comparison,{...expected,current_version:3});
      throw new Error('accepted wrong version');}
 catch(error){assert(error.message!=='accepted wrong version','version mismatch rejected');}
 assert(host.hidden&&!host.childNodes.length,'comparison rejection clears');
 const events=await (await fetch('/events.json')).json();
 const eventOptions={workspaceId:plan.inputs.workspace_id,planId:plan.inputs.plan_id};
 const eventResult=renderPlanEvents(host,events,eventOptions);
 assert(eventResult.lastSequence===3&&eventResult.nextCursor==='more-history','history paging');
 assert(host.textContent.includes('Customer Report Retracted'),'retraction separate');
 assert(host.textContent.includes('Customer Reports Applied'),'immutable original preserved');
 assert(host.textContent.includes('Not Independently Verified'),'report provenance');
 assert(host.textContent.includes('This page is incomplete'),'pagination disclosure');
 assert(host.textContent.includes('<img src=x>')&&!host.querySelector('img,script,a,button,input'),
        'history literal text only');
 assert(host.textContent.includes(events.items[1].event.event_id),'superseded event reference');
 for(const alter of [
   value=>{value.items[0].event.workspace_id=999999;},
   value=>{value.items[0].event.advertising_writes_enabled=true;},
   value=>{value.items[1].event.verification='provider_verified';},
   value=>{value.items[1].event_sequence=1;},
   value=>{value.items[2].event.supersedes_event_id=null;},
   value=>{value.items[1].event.reported_applied_at='2099-01-01T00:00:00Z';},
 ]){
   const invalid=structuredClone(events);alter(invalid);
   try{renderPlanEvents(host,invalid,eventOptions);throw Error('accepted malformed history');}
   catch(error){assert(error.message!=='accepted malformed history','history rejection');}
   assert(host.hidden&&!host.childNodes.length,'history failure clears');
 }
 renderPlanEvents(host,{...events,items:[events.items[2]],next_cursor:null},
                  {...eventOptions,afterSequence:2});
 assert(host.textContent.includes('Continuation after event 2'),'continuation context');
 assert(host.textContent.includes('End of the returned history'),'page ending');
 const observations=await (await fetch('/observations.json')).json();
 const observationOptions={workspaceId:observations.items[0].event.workspace_id,
                           planId:observations.items[0].event.plan_id};
 const mixedResult=renderPlanEvents(host,observations,observationOptions);
 assert(mixedResult.lastSequence===6&&mixedResult.nextCursor===null,'mixed history sequence');
 for(const label of ['Customer Reports Applied','Customer Report Retracted',
     'Observed Match — Supported Fields Only','Observed Conflict','Observation Unavailable',
     'Causality Not Assessed','Historical Source Interval','Evidence Expiry',
     'does not recompute their digests','Expected: paused','Observed: enabled','Unavailable:'])
   assert(host.textContent.includes(label),'missing observation label '+label);
 assert(!host.textContent.includes('Invalid Date'),'no invented observation recorded time');
 const items=host.querySelectorAll('li');
 assert(!items[3].textContent.includes('Customer ID')&&
        !items[3].textContent.includes('Replaces Event'),'no invented actor or supersession');
 assert(items[1].textContent.includes('Not Independently Verified'),
        'matching observation does not verify customer report');
 // Historical comparison is valid even though its source has expired by viewing time.
 assert(observations.items[3].event.observed_at==='2026-10-01T01:20:00Z','historical fixture');
 const values=await (await fetch('/observation-values.json')).json();
 for(const event of values){
   renderPlanEvents(host,{...observations,items:[{...observations.items[3],event}]},
                    observationOptions);
   const expected=event.comparisons[0].expected.value;
   assert(host.textContent.includes(Array.isArray(expected)?expected.join(', '):expected),
          'typed field values visible');
   assert(!host.querySelector('a,button,input'),'values do not create links or controls');
 }
 const precise=structuredClone(observations);
 precise.items[3].event.observed_at='2026-10-01T01:20:00.000002Z';
 const preciseSource=precise.items[3].event.comparisons[0].evidence.source;
 preciseSource.observation_started_at='2026-10-01T01:20:00.000001Z';
 preciseSource.observed_at='2026-10-01T02:20:00.000001+01:00';
 preciseSource.expires_at='2026-10-01T01:20:00.000003Z';
 renderPlanEvents(host,precise,observationOptions);
 assert(host.textContent.includes('Observed Match'),'valid microsecond and offset history');
 const legacy=structuredClone(observations);
 legacy.items[5].event.comparisons[0].evidence=structuredClone(
   observations.items[3].event.comparisons[0].evidence);
 renderPlanEvents(host,legacy,observationOptions);
 assert(host.textContent.includes('Observation Unavailable'),'legacy missing value with evidence');
 const literal=structuredClone(observations);
 literal.items[3].event.limitations[0]='<img src=x onerror="window.injected=true">';
 literal.items[3].event.comparisons[0].evidence.target.display_name='<script>bad</script>';
 renderPlanEvents(host,literal,observationOptions);
 assert(host.textContent.includes('<img src=x')&&host.textContent.includes('<script>bad'),
        'literal observation text');
 assert(!host.querySelector('img,script,a,button,input')&&!window.injected,'safe observation DOM');
 for(const alter of [
   e=>{e.workspace_id=999999;},e=>{e.plan_id='9'.repeat(32);},
   e=>{e.advertising_writes_enabled=true;},e=>{e.spending_authority='approved';},
   e=>{e.actor_id='a'.repeat(32);},e=>{e.recorded_at=e.observed_at;},
   e=>{e.supersedes_event_id=null;},e=>{e.decision='deferred';},
   e=>{e.assertion='customer_reports_applied';},e=>{e.causality='confirmed';},
   e=>{e.applied_by='inlet';},e=>{e.status='conflicting';},
   e=>{e.observed_at='not a date';},e=>{e.observed_at='2026-10-01T01:20:00';},
   e=>{e.comparisons[0].expected.value='active';},
   e=>{e.comparisons[0].observed.field='landing_page';},
   e=>{e.comparisons[0].observed=null;},
   e=>{e.comparisons[0].unavailable_reason='Missing';},
   e=>{e.comparisons[0].evidence=null;},
   e=>{e.comparisons.push(structuredClone(e.comparisons[0]));},
   e=>{e.limitations=[];},e=>{e.limitations=['x'.repeat(2001)];},
   e=>{e.comparisons[0].evidence.source.workspace_id=99;},
   e=>{e.comparisons[0].evidence.source.account.account_id=99;},
   e=>{e.comparisons[0].evidence.source.account.connection_version='foreign';},
   e=>{e.comparisons[0].evidence.target.provider_reference.platform='meta_ads';},
   e=>{e.comparisons[0].evidence.target.provider_reference.parent_campaign_id='1';},
   e=>{e.comparisons[0].evidence.source.kind='reported_metrics';},
   e=>{e.comparisons[0].evidence.source.coverage='unavailable';},
   e=>{e.comparisons[0].evidence.source.key='foreign';},
   e=>{e.comparisons[0].evidence.source.document_digest='not-a-digest';},
   e=>{e.comparisons[0].evidence.source.observed_at='2026-10-01T01:21:00Z';},
   e=>{e.comparisons[0].evidence.source.expires_at=e.observed_at;},
   e=>{e.comparisons[0].evidence.source.observation_started_at='2099-01-01T00:00:00Z';},
   e=>{e.comparisons[0].evidence.source.observation_started_at='2026-02-30T00:00:00Z';},
   e=>{e.observed_at='2026-10-01T01:20:00.000001Z';
       e.comparisons[0].evidence.source.observed_at='2026-10-01T01:20:00.000002Z';},
   e=>{e.comparisons[0].evidence.source.observation_started_at='2026-10-01T01:16:00.000002Z';
       e.comparisons[0].evidence.source.observed_at='2026-10-01T01:16:00.000001Z';},
   e=>{e.comparisons[0].evidence.extra=true;},
   e=>{e.comparisons[0].evidence.source.extra=true;},
   e=>{e.comparisons[0].evidence.target.extra=true;},
   e=>{e.comparisons[0].evidence.target.provider_reference.extra=true;},
   e=>{delete e.comparisons[0].evidence.source.reporting_window;},
   e=>{delete e.comparisons[0].evidence.target.budget_owner_key;},
   e=>{delete e.comparisons[0].evidence.target.provider_reference.parent_campaign_id;},
   e=>{e.comparisons[0].evidence.source.reporting_window={
       starts_at:'2024-01-01T00:00:00Z',ends_at_exclusive:'2026-01-01T00:00:00Z'};},
   e=>{e.comparisons[0].evidence.source.reporting_window={
       starts_at:'2026-01-01T00:00:00Z',ends_at_exclusive:'2026-02-01T00:00:00Z',extra:true};},
 ]){
   const invalid=structuredClone(observations);alter(invalid.items[3].event);
   renderPlanEvents(host,observations,observationOptions);
   try{renderPlanEvents(host,invalid,observationOptions);throw Error('accepted observation');}
   catch(error){assert(error.message!=='accepted observation','observation rejection');}
   assert(host.hidden&&!host.childNodes.length,'entire mixed page cleared');
 }
 for(const alter of [
   p=>{p.items[4].event_sequence=4;},
   p=>{p.items[4].event.event_id=p.items[3].event.event_id;},
   p=>{p.items[5].event.comparisons[0].unavailable_reason=null;},
   p=>{p.items[0].event.observed_at=p.items[3].event.observed_at;},
   p=>{p.next_cursor='';},
 ]){
   const invalid=structuredClone(observations);alter(invalid);
   try{renderPlanEvents(host,invalid,observationOptions);throw Error('accepted mixed page');}
   catch(error){assert(error.message!=='accepted mixed page','mixed page rejection');}
   assert(host.hidden&&!host.childNodes.length,'mixed page atomic rejection');
 }
 renderPlanEvents(host,{...observations,items:observations.items.slice(3)},
                  {...observationOptions,afterSequence:3});
 assert(host.textContent.includes('Continuation after event 3'),'observation continuation');
 clearPlanEvents(host);assert(host.hidden&&!host.childNodes.length,'history clear');
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
