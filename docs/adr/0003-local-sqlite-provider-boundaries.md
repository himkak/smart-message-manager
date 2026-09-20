# ADR 0003: Use SQLite locally behind repository protocols

## Status
Accepted.

## Decision
The first persistence adapter will use SQLite for local development; callers depend only on async repository protocols.

## Consequences
Local setup stays low-cost and easy. A Cosmos DB adapter can be introduced later without coupling application services to SQL.

