# Ad Analyzer workspace architecture

## Canonical names

| Term | Meaning |
|---|---|
| **Ad Analyzer** | The complete shared platform: dashboard, API, workers, database, analysis, recommendations, and execution controls. |
| **Denticode Ad Analyzer** | The Denticode client workspace inside Ad Analyzer. |
| **Workspace** | The top-level client security, configuration, and data boundary. |
| **Advertising account** | A Google Ads or Meta Ads account connected to one workspace. It is a data source, not a client boundary. |

## Ownership model

Each workspace owns:

- analysis, automation, notification, and branding configuration;
- memberships and roles;
- integration registrations and secret-manager references;
- advertising accounts and their descendant campaign data;
- conversion events, synchronization job runs, findings, and recommendations;
- the measurement contract, funnel-stage definitions, and source-event mappings;
- CRM connections and the CRM records reached through those connections.

IDs remain platform-global, but all top-level queries and writes carry a `workspace_id`. Compound
foreign keys prevent a job run, recommendation, or finding from naming an advertising account in a
different workspace. Descendant advertising entities inherit their workspace through their
advertising account. CRM descendants inherit it through their workspace-owned connection.

## Authorization

| Role | View workspace | Review findings | Approve/reject/dry-run |
|---|---:|---:|---:|
| Platform administrator | Yes, all workspaces | Yes | Yes |
| Workspace owner | Yes | Yes | Yes |
| Workspace administrator | Yes | Yes | Yes |
| Workspace analyst | Yes | Yes | No |
| Workspace viewer | Yes | No changes | No |
| No active membership | No | No | No |

Google IAP authenticates the human identity. Ad Analyzer then authorizes that identity against
`workspace_memberships`. Platform administrators are configured separately. Unauthorized
workspace lookups return `404` so the existence of another client's workspace is not disclosed.
The bearer-token API remains a platform-operator interface; client-facing API credentials must use
workspace-scoped principals before they are introduced.

## Integration boundary

`workspace_integrations` stores safe integration metadata and a reference to externally managed
credentials. API responses expose only whether a credential reference exists, never the reference
or secret value. Provider-specific connection rows, such as `crm_connections`, point back to both
the workspace and the integration registration.

Inbound CRM events are stamped with the configured workspace before they enter Pub/Sub. The worker
selects an active CRM connection only within that workspace. Future GA4, CRM, Google Ads, Meta Ads,
and notification connections must follow the same pattern.

## Measurement boundary

Each workspace owns one measurement contract. The contract identifies the authoritative business
source, distinguishes diagnostic platform conversions from CRM-confirmed outcomes, defines the
funnel stages and event mappings, and records attribution and customer-value windows. The contract
is read-only through the operator API and remains fail-closed while it is a draft. See
[the measurement contract](measurement-contract.md).

## Existing Denticode deployment

Migration `20260802_0008` creates the workspace structure, seeds the `denticode` workspace as
**Denticode Ad Analyzer**, and backfills all existing client-owned records into it. It also creates
initial integration registrations from existing advertising and CRM connections.

Legacy resource names, the repository name, the database name `denticode_ads_optimizer`, and
existing `DENTICODE_*` environment aliases remain supported to avoid an unnecessary production
cutover. New platform settings use `AD_ANALYZER_*` names where a compatibility-safe alias is
available.

The migration downgrade refuses to collapse the schema when more than one workspace exists. This
prevents a rollback from silently merging client boundaries.

## Adding another client

Provisioning another client requires an explicit, audited workflow that:

1. creates one workspace and workspace configuration;
2. creates active memberships with least-privilege roles;
3. registers integrations using external secret references;
4. connects advertising accounts with the new workspace ID;
5. configures collectors and CRM routing with that workspace ID;
6. verifies cross-workspace denial and duplicate external-account isolation;
7. creates and explicitly approves that client's measurement contract;
8. leaves advertising writes disabled until that workspace has separately approved controls.

No client should be added by copying Denticode credentials, memberships, global settings, or
database rows.
