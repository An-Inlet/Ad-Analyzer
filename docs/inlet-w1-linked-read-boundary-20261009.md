# Current Linked TikTok Read Boundary Qualification

Base `5aba7e0`. Three current GET-reader functions receive only explicit
`planning_boundary` and existing `read_only_graph` fixture use, plus the explicit
fixture import in their two modules. No retained-execution marker or capability
patch is added. They already consume the reviewed source-only TikTok prepare helper.

Original function bodies, parameters, decorators and other statements remain
identical; the AST proof removes only the two added decorators and fixture imports.
Current before/after checks require zero advertising authority records. Actual
vault/session/generation, close-time invalidation, GET shape, bounded pagination,
exact decimal, null-vs-absent and no-secret assertions remain unchanged.

Evidence directory:
`/workspace/inlet-evidence/20261009/w1-linked-read-boundary/`.

The initial shell created the correct isolated worktree but mistakenly retained
`/workspace/inlet-w1-followup` as cwd for the edit/test commands. Only this package's
six decorators and two fixture imports touched that checkout. The exact additions
were transferred to the intended worktree and removed from root; root was verified
clean at `f2099ac08c26877bcfb4c5f8912e2e302bb7be1e`. The wrong-checkout run was
intentionally interrupted with SIGINT; `focused.log/xml/exit` records25 completed
passes,24.96s,exit2. It is **not qualification**, including because edits were removed
before the running process was stopped. It involved only fixture-isolated schemas,
not the aggregate database. The correction and interruption were reported promptly.

The qualification invocation is separate, with explicit cwd
`/workspace/inlet-w1-linked-read-boundary`, verified HEAD`5aba7e0`:

```sh
PATH=/workspace/inlet-venv/bin:$PATH \
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
python -m pytest tests/test_tiktok_linked_capabilities.py \
  tests/test_tiktok_linked_posts_owned.py --tb=short --maxfail=2 \
  --junitxml=/workspace/inlet-evidence/20261009/w1-linked-read-boundary/qualified.xml
```

No application, shared fixture, provider call, Full or workflow change. No original
frozen aggregate result is revised;42 failures may be credited only from the exact
qualified successor identity intersection and independent review.

Terminal isolated qualification: **47 passed, zero failures/errors/skips,59.42s**.
This includes42 exact original failed identities plus five already passing pure
transport-boundary cases, verified separately in `coverage.json`. The interrupted
25-pass run overlaps and is not added. Whole Ruff passed; bare mypy passed1134
source files; diff check passed. Final AST comparison against committed base again
confirmed original bodies/parameters/decorators unchanged after stripping only
these additions. `qualified.log/xml/exit`, `ruff.log`, `mypy.log/exit` and
`ast-preservation.json` retain evidence. Independent review remains required.
