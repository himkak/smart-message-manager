# ADR 0001: Use a modular monolith for V1

## Status
Accepted.

## Decision
Ship one FastAPI application with explicit connector, repository, search, RAG, API, and future-agent boundaries.

## Consequences
This is simple to run and deploy to Azure Container Apps while keeping provider adapters replaceable. Separate deployable services are deferred until a concrete scaling or ownership need exists.

