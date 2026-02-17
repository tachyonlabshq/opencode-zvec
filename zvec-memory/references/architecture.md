# zvec-memory Architecture

This document explains how the skill implements hybrid long-term memory for OpenCode.

## Goals

- Keep global memory in `~/.opencode/memory/global`
- Keep project memory in `<workspace>/.memory/zvec-memory`
- Store important interactions in full detail
- Compress medium-value interactions
- Prune stale low-value memory safely
- Prefer fast/cheap OpenRouter embeddings, with local and deterministic fallback

## High-Level Design

1. Input text arrives from MCP tool or CLI wrapper.
2. Importance scorer evaluates value (0-100).
3. Tier policy chooses `full`, `summary`, or `skip`.
4. Embedding router generates vector.
5. Memory is written to chosen scopes (`global`, `project`, or both).
6. Query uses semantic similarity and returns ranked memories.
7. Access metadata is updated for later pruning decisions.

## Storage Layers

### Primary Backends

- `ZvecBackend` when zvec is available
- `JsonBackend` fallback for portability

### Why Keep Metadata Sidecar with zvec

zvec APIs can evolve between versions. Metadata sidecar ensures stable behavior across runtime environments and keeps query fallback deterministic when vector query API shape differs.

## Embedding Strategy

Priority order:

1. OpenRouter (`/api/v1/embeddings`)
2. Local sentence-transformers model
3. Deterministic hashed embedding

Design intent:

- OpenRouter keeps latency/cost efficient for most cases
- Local model allows offline operation
- Hashed fallback prevents hard failure if dependencies or network are unavailable

## Importance and Tiering

Thresholds:

- Keep threshold: 40
- Full threshold: 70

Behavior:

- `< 40` => not stored
- `40..69` => compressed summary + key details
- `>= 70` => full text retained

## Pruning Model

A record is removed only when all conditions hold:

- Importance is below threshold
- Last access is older than age cutoff
- Access count is zero

This avoids deleting frequently used memory even when old.

## Project Boundary

Project scope is defined by workspace root as resolved by OpenCode/workspace environment. This maps memory to active project folders and avoids bleeding context across unrelated repos.

## Build Safety of `.memory`

The `.memory` directory is hidden and data-only. It does not impact compilers in normal workflows. Add `.memory/` to `.gitignore` to keep it out of version control and CI artifacts.
