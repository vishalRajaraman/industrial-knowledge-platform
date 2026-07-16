# Baseline API Gateway

This directory contains the isolated Layer 5 API Gateway baseline.

## Scope

- FastAPI edge layer only
- No auth, RBAC, or business logic
- Stub endpoints for search and system health
- Clean separation from ingestion, MCP, orchestrator, and storage services

## Routes

- `POST /api/v1/search/vector`
- `POST /api/v1/search/graph`
- `GET /api/v1/system/health`

## Run

```bash
uvicorn api_gateway.baseline.app.main:app --host 0.0.0.0 --port 8100 --reload
```
