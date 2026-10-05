# Inlet Public Page — Omnisend Update

This is the existing v2 public marketing page, prepared for the owner's publication
on Aninlet.com. It is independent of B01 diagnostics and B02–B04 customer-foundation
work. Signup, subscriptions, account connections and advertising operations are
not implemented by this page. Nothing has been published by this change.

## Use The Files

- `Inlet-Squarespace-Code-v2.txt`: copy the entire file into one Squarespace HTML
  Code Block with Display Source off. Replace the previous entire block; do not
  install twice. Use GitHub's **Copy raw file** or **Download raw file** control.
- `Inlet-Page-Preview-v2.html`: download and open in a browser for the standalone
  preview. The preview embeds the exact same block. The installed block inherits
  the site's fonts; the standalone file uses its original fallback fonts.

Preview the installed block before publishing, including external logos and actual
site fonts. The owner controls Squarespace publication; this repository change
neither publishes nor changes customer advertising accounts.

## What Changed

- Salesforce names, links, classes and two image references become Omnisend.
- Integration note and FAQ name Klaviyo, HubSpot and Omnisend as the three planned
  customer-data connections for Shopify brands using Google Ads, Meta Ads and
  TikTok Ads. Integrations remain explicitly not live.
- FAQ explicitly requires customer review before publishing new campaigns or
  creative. Illustrative demo and email-only early-access CTA remain intact.
- A separate small enhancement shows readable brand names when logo images fail,
  then restores the real image if it loads. It does not draw replacement logos.

An Inlet's original real-logo references, parent-header logo inheritance, website
font inheritance, green palette, Title Case headings, graphics, FAQ structure and
original demo JavaScript are preserved. Demo behavior is local-only; no inputs are
saved, submitted, or interpreted by an AI service.

## Source Provenance

The complete original native Library files were read in paginated full-text reads,
including every final line. Reconstructed byte sizes matched the authoritative
metadata exactly, including final newlines. The original HTML embedded the exact
TXT block. No ZIP recovery or design recreation was used.

| Original Source | Bytes / Lines | SHA-256 |
| --- | --- | --- |
| Inlet-Squarespace-Code-v2.txt | 82,602 / 862 | `c9e768b8b489f313332a3e320134dce5d421b7d90e52ccaa3e04286025e54967` |
| Inlet-Page-Preview-v2.html | 83,373 / 866 | `81fcd0391704415091415aa3fe1ed554d68842f370885f84aad333d1b2151402` |

Original Library IDs: `libfile_64edccbffc608191bf1fa559d2242bea` (TXT),
`libfile_44cbe3e5d3a08191bd3c8569310d9e6e` (HTML).

## Logo Evidence And Limits

Omnisend's [official brand-assets page](https://www.omnisend.com/brand-assets/)
links its primary-logo image at
`https://www.omnisend.com/wp-content/themes/omnisend-v2/assets/img/brand/Brand-assets-LP-logo_Omnisend-logo-primary.png`.
The image URL was taken from that page, not guessed or generated.

The execution environment's proxy denied the connection to that host before an
upstream response (`CONNECT 403` / `ERR_TUNNEL_CONNECTION_FAILED`). The An Inlet
Squarespace image host and Shopify's primary-logo host were also blocked. This is
**not evidence of an origin HTTP 404 or a broken image URL**. The permitted web
reader confirms the official page's reference but supplies no usable image pixels
or origin status here. Omnisend logo pixel/render acceptance remains unverified.

An observational browser run loaded 11 of 19 image elements. The eight blocked
elements were five An Inlet logos, one Shopify logo and two Omnisend logos. Their
readable fallbacks now preserve names when loading fails. Verify real logo loading
in the owner's Squarespace preview; do not claim this environment verified it.

## Reproduce The Checks

With Node 24 and npm, from this directory:

```sh
npm ci --prefix checks
cd checks
npx playwright install chromium
npm test
```

For an existing Chromium installation:

```sh
CHROMIUM_EXECUTABLE=/usr/bin/chromium npm --prefix checks test
```

The default check blocks external requests intentionally so it is deterministic
and verifies graceful fallback. It serves the preview on a temporary loopback
port, checks script syntax and TXT/HTML parity, then exercises:

- six viewport widths: 320, 390, 768, 1024, 1440 and 1920px, without horizontal overflow;
- inert goal-text rendering, including an HTML-injection sample;
- all three modes at $500, $15,000 and $50,000, preserving the selected spending limit;
- reset to the original goal, $10,000 and Balanced;
- FAQ expansion, early-access mailto link, keyboard focus and reduced-motion navigation;
- failed-logo names and successful-load event recovery;
- no demo fetch/XHR/WebSocket activity, form submission or browser storage;
- a synthetic Squarespace parent's font and logo-URL inheritance;
- JavaScript-disabled content, FAQs and email CTA; zero script errors.

`CHECK_EXTERNAL_ASSETS=1` permits an optional observational image-loading run.
Its counts describe that environment only; it is not a substitute for the
owner's installed-site preview. `.github/workflows/inlet-public-page.yml` runs
these deterministic checks for changes to this page. It does not deploy.

## Delivery And Review Record

Branch starts from main `ea3591c5086fbf2cee8038bf9208ac7f0050de75` and is independent
of B01's diagnostic changes. The policy limits *dependent* product PRs; this public
page correction does not start B02 or bypass its architecture/merge gates.

Main's dated Shopify fixture failed during required Python checks. The exact
already-verified maintenance fix from B01 is included independently: freeze that
test's clock and constrain SQLAlchemy to its compatible 2.0 series. No diagnostic
or customer-foundation change is included. These two maintenance changes are
identical across branches and introduce no dependency on B01 being merged first.

Native Library saving is still blocked: the prescribed helper failed before upload
preparation with `hosted apps tools/list request failed: network`, including one
permission-expanded retry. Original Library versions were not changed; no direct
replacement fallback or additional upload attempt was made. GitHub is the durable
delivery route for these files. No new source upload from the owner is needed.

Local validation on 2026-10-05: `python -m pytest` — 586 passed, 12 skipped
(six PowerShell checks unavailable and six disposable-PostgreSQL checks without
their explicit environment configuration); `ruff check .` — passed; `mypy` —
passed for 159 source files; `git diff --check` — passed. Chromium browser checks
passed at all six widths with zero script errors. Hosted CI status is recorded in
the draft pull request rather than presumed from local results.

Reviewed screenshots show the environment's readable logo fallbacks, not verified
remote logo pixels: [integration strip](review/integration-strip.png) and
[mobile preview](review/mobile-preview.png). They document the actual rendering
inspected during this delivery.
