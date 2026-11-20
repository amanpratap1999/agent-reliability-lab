# Agent Adapter Contract — v1

## Purpose

Define one provider-neutral asynchronous contract so the execution engine can work with different agent implementations without importing provider-specific SDKs or assuming one agent framework.

No concrete API, Python, MCP or browser adapter is registered in this milestone. This commit defines the contract and its fake-adapter verification only.

## Lifecycle

Every adapter implements the runtime-checkable AgentAdapter protocol:

1. connect(config, runtime_context) — validate configuration and establish a session.
2. execute(task, runtime_context) — execute one task and return an AgentExecutionResult envelope.
3. collect_events() — return currently available normalized AdapterEvent records.
4. stop() — request cooperative cancellation; it is a request, not proof that execution has stopped.
5. disconnect() — release resources and be safe to call after normal completion, stop or failure.

The later execution runner owns the configured wall-clock timeout, applies it to connect/execute, maps timeout/cancellation to normalized error codes, and calls disconnect during cleanup. A stop request is not considered completed until the execution result/runner confirms cancellation.

## Typed contracts

- AdapterConfig: neutral adapter type, config version, bounded timeout/action budget, non-secret settings and secret references.
- AdapterRuntimeContext: run/environment identifiers and runtime metadata.
- AgentTask: task/scenario identifiers, instruction and task context.
- AgentExecutionResult: explicit completed/failed/timed_out/cancelled/inconclusive status, output envelope, normalized error and timing metadata.
- AdapterCapabilities: event collection, cooperative stop, structured tool-call and screenshot support, concurrency limit and observability notes.
- AdapterEvent: timestamped event with an explicit provenance value.

Secret material must not be placed in settings. AdapterConfig accepts secret references (vault://, env://, secret:// or op://), not credential values.

## Provenance

The contract keeps four provenance values distinct:

- directly_observed — captured independently from the environment or instrumentation.
- adapter_reported — reported by the adapter integration.
- agent_reported — claimed by the agent itself.
- inferred — derived from other evidence.

An agent-reported completion must never be upgraded to directly observed truth by the adapter.

## Normalized errors

AdapterErrorCode values:

- configuration_invalid
- connection_failed
- execution_failed
- timeout
- cancelled
- unsupported_capability
- protocol_error
- unknown

Timeout and connection failures are retryable by default. Cancellation, invalid configuration, unsupported capability and unknown failures are not automatically retryable. Adapter-specific exceptions can be wrapped in AdapterError to preserve a stable code and safe details. Unknown exception messages are not copied into the normalized message, avoiding accidental leakage of credentials or private endpoints.

## Registry

AdapterRegistry registers a factory with AdapterMetadata under a neutral adapter_type key. Duplicate registration is rejected unless replacement is explicit. Creation verifies that the returned object satisfies AgentAdapter. The registry contains no provider-specific branching.

## Contract tests

The fake adapter tests cover runtime protocol conformance, all five lifecycle methods, typed task/result/event handling, explicit provenance, registry registration/lookup/duplicate handling, invalid adapter factories, configuration validation and normalized timeout/cancellation/connection/protocol errors.


## Verification evidence

GitHub Actions run #16 passed on Ubuntu and Windows: 49 tests on each runner, all three Alembic migrations, and Uvicorn liveness/database-readiness smoke tests returning HTTP 200.

This verifies the contract, fake adapter and registry only. No production/provider adapter is registered or claimed as implemented in D13.
