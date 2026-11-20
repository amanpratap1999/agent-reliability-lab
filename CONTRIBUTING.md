# Contributing

- Read the canonical project blueprint before architectural changes.
- Keep the application a modular monolith.
- Do not introduce Docker as a local-development requirement.
- Do not add mandatory paid APIs or model dependencies.
- Never store hidden chain-of-thought.
- Preserve observed, reported and inferred evidence distinctions.
- Never report success when verification is missing or inconclusive.
- Keep safety outcomes separate from task scores.
- Implement roadmap phases sequentially.

## Workflow
1. Make a focused change.
2. Add or update tests.
3. Run pytest and Alembic migration checks through CI.
4. Inspect the GitHub Actions result.
5. Document behavior and limitations.
6. Do not mark work complete without verifiable evidence.
