"""Same-origin OAuth callback relay preserving Strict session-cookie protection."""

import base64
import hashlib

from fastapi import Response


def callback_relay() -> Response:
    from fastapi.responses import HTMLResponse

    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Connect Google Ads — Inlet</title><h1>Connect Google Ads</h1>
<p id="result">Completing authorization…</p>
<script>
const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
sessionStorage.setItem('inlet-oauth-state:' + location.pathname, params.get('state') || '');
const csrf = document.cookie.split('; ').find(x => x.startsWith('__Host-inlet_csrf='));
const codes = [...params.getAll('auth_code'), ...params.getAll('code')];
if (params.getAll('state').length === 1 && codes.length === 1) {
fetch(location.pathname, {method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','X-CSRF-Token':csrf ? csrf.split('=')[1] : ''},
  body:JSON.stringify({state:params.get('state'),code:codes[0]})})
.then(async r => {const data = await r.json();
  document.getElementById('result').textContent = r.ok
    ? 'Authorization received. Return to Connections to select an account.'
    : 'Connection unavailable. Return to Connections and try again.';
}).catch(() => {
  document.getElementById('result').textContent='Connection unavailable. Please restart.';
});
} else {document.getElementById('result').textContent='Invalid callback. Restart connection.';}
</script></html>"""
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; connect-src 'self'; "
            f"script-src 'sha256-{script_hash}'; base-uri 'none'; frame-ancestors 'none'",
        },
    )
