# AI workflow

Start a manual run with `POST /api/v1/workflows/start`. The service normalizes the
input, generates positive/negative/boundary scenarios, validates them with the
documented weighted score, generates test cases, validates those cases, and exposes
the result at `GET /api/v1/workflows/{workflow_id}/result`.

Validation scores are calculated in Python and pass at `0.95`. A failed stage is
retried at item level up to three attempts and then enters `scenario_manual_review`
or `testcase_manual_review`. Submit feedback and corrected data to the `resume`
endpoint to continue from that stage. Status polling and SSE events are both
available. Database-mode input is loaded through Person 2's `DatabaseInputSource`.

The provider abstraction accepts a primary and optional fallback provider. Tests
use deterministic agents and never call a real model or consume tokens.
