# ADR 0002: Normalize sources into a canonical message model

## Status
Accepted.

## Decision
Represent communications using a source-independent `Message` and `Conversation`, with stable source-scoped identifiers and flexible metadata.

## Consequences
Gmail details remain in the Gmail connector and metadata. WhatsApp and SMS can be introduced without changing retrieval or RAG contracts.

