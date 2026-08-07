<!-- @mutagent/helix boot -->
# Helix — MutagenT ADL conductor

This project has the Helix orchestrator installed. To boot it, read and adopt the agent
definition at `.claude/skills/mutagent-helix/orchestrator.md` (run its activation-instructions: persona → system index →
ADL dashboard), then await a `*command`.

Trigger: `*mutagent` · `/mutagent-helix` · `boot`.
<!-- @mutagent/helix boot -->

<!-- Project Victorious note — outside the @mutagent/helix boot markers above. -->

The Helix installation itself is **not committed** (`.gitignore`): it is
third-party, partly proprietary, and vendors ~23MB of `node_modules`. Restore it
with `npx mutagent install helix`.

Helix is development-time tooling only. It is never called at runtime — see
[ADR-0013](docs/adr/0013-engineering-review-layer.md) and
[`docs/07_System_Architecture.md`](docs/07_System_Architecture.md).
