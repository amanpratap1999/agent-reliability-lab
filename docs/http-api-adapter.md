# HTTP API Agent Adapter

## Scope

HttpApiAdapter is a provider-neutral bridge for an agent exposed through a JSON HTTP API. It does not depend on a vendor SDK, framework, or paid provider. D14 verifies the integration against an in-process FastAPI mock server; it does not claim a production agent endpoint has been connected.

## Configuration

The adapter consumes the common AdapterConfig envelope:

- adapter_type must be http_api.
- timeout_seconds and max_actions are bounded and sent as execution limits.
- settings contains HttpApiAdapterSettings: base_url, execute_path, optional events_path and stop_path, auth header/scheme, safe non-secret headers and capability flags.
- secret_refs contains references only. The configured auth_ref_key selects a reference resolved at runtime by an injected SecretResolver.

HTTPS is required except for loopback mock/test endpoints. Base URLs cannot embed credentials, query strings or fragments. Paths must remain on the configured host and cannot traverse parent directories. Redirects are disabled. Authentication values are never stored in settings or logged. Custom headers cannot override authentication, cookie or transport-controlled headers.

## Request contract

POST execute_path receives a Pydantic-validated HttpApiExecutionRequest:

~~~json
{
  "task": {
    "task_id": "task-123",
    "scenario_id": "SD-001",
    "instruction": "Find and assign INC1001",
    "context": {}
  },
  "context": {
    "run_id": "run-123",
    "environment_id": "servicedesk_v1",
    "metadata": {}
  },
  "limits": {
    "timeout_seconds": 120,
    "max_actions": 100
  }
}
~~~

## Response contract

The endpoint must return a JSON HttpApiAgentResponse with a supported execution status (completed, failed, timed_out, cancelled or inconclusive), optional output/error, events, timestamps and metadata. Missing or malformed required fields become a normalized protocol error.

If events_path is configured, collect_events() performs GET events_path?run_id=<current-run-id> and merges those records with events returned by execute. If stop_path is configured, stop() POSTs the current run ID. Without stop_path, cooperative_stop is false and stop() raises unsupported_capability. A stop request is not proof that the remote execution has stopped.

## Provenance and error mapping

- The returned task output is always marked agent_reported.
- Every event record returned by the remote API is marked adapter_reported, regardless of any provenance field the remote response attempts to supply.
- This adapter does not emit directly_observed events; environment truth belongs to the independent verifier.
- HTTP 401/403 → authentication_failed.
- HTTP 408/504 or client timeout → timeout.
- HTTP 400/422 or malformed JSON/schema → protocol_error.
- HTTP 429/5xx → retryable execution_failed.
- Connection/request errors → retryable connection_failed.

Known authentication material is redacted from output, metadata, event payloads and remote error details/messages before returning them. Error messages do not include response bodies or request headers.

## Verification

The test suite uses httpx ASGITransport with a local FastAPI mock server. It verifies request serialization, auth-reference resolution, response validation, event provenance, event collection, stop behavior, output redaction, auth failure, malformed responses, timeouts, server failures, connection failures and transport/path validation.
