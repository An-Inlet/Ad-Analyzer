# Windows PowerShell bootstrap fix

The production-operations bootstrap now:

- checks GitHub CLI authentication before changing Google Cloud resources;
- probes for optional Google Cloud resources without allowing expected `NOT_FOUND` responses to terminate Windows PowerShell when `$ErrorActionPreference` is `Stop`;
- remains idempotent and creates no service-account key.
