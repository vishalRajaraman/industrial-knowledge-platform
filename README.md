# Industrial Knowledge Platform (IKP)

**[🎥 Watch the Demo Video Here!](https://1drv.ms/v/c/566039cec60bfa00/IQBRbf_lg39-QoGxpd2as9Y-Aby_FwIZ9fion5WnjtECx00?e=LeFSOk)**

The Industrial Knowledge Platform is an AI-powered operational intelligence layer designed to streamline knowledge retrieval, ensure regulatory compliance, and proactively identify safety patterns in industrial environments.

## Overview

IKP integrates diverse data sources (from unstructured text to P&ID diagrams) into a unified Knowledge Graph and Vector Database, making them instantly queryable through role-aware AI Agents.

### Key Features
- **Multi-Modal Data Ingestion**: Supports local directory and S3 bucket uploads for manuals, Excel files, layout drawings, and P&ID diagrams.
- **Advanced Processing Pipeline**:
  - **NER (Named Entity Recognition)** for extracting entities and relationships from textual documents.
  - **YOLO Vision Model** for accurate P&ID diagram recognition and asset mapping.
- **Robust Storage Architecture**:
  - **Vector Database** for dense semantic search and RAG contexts.
  - **Knowledge Graph (Neo4j)** for modeling complex asset relationships and compliance linkages.
  - **Document Store** for raw file archiving.
- **AI Orchestrator & Agents Layer**:
  - **Router Agent**: Analyzes user intent and dynamically routes the query to the correct sub-agent.
  - **Copilot Agent**: General knowledge retrieval using Hybrid Search (Vector + Graph) and RAG for deep technical troubleshooting.
  - **Compliance Agent**: Executes regulatory gap detection and compiles automated audit evidence packages.
  - **Lessons Agent**: Analyzes historical near-misses and generates proactive safety alerts based on patterns.
- **Role-Based Access Control (RBAC)**: Secure access portals tailored for `plant admin` and `engineer` roles.

## Architecture Workflow

1. **Ingestion**: Raw files (Text/Images) flow through data processors into NER and YOLO models.
2. **Storage**: Extracted embeddings go to the Vector DB; Nodes, edges, and asset mappings go to the Knowledge Graph.
3. **Orchestration**: The user submits a query via the Frontend API. The Router Agent classifies intent and delegates tasks to specialized Agents (Copilot, Compliance, Lessons), which retrieve context from the storage layer and synthesize a final response.

## Getting Started

1. **Backend**: Start the MCP server and API Gateway.
2. **Frontend**: The web portal is built on Next.js. Start the frontend via `npm run dev` in the `frontend` directory.
3. **Login**: Use the Gateway Auth Portal to log in as a Plant Admin or Engineer.

## Tech Stack
- **Frontend**: Next.js, React, TailwindCSS
- **Backend**: Python, FastAPI, MCP (Model Context Protocol)
- **AI / ML**: Mistral, YOLO, GLiNER
- **Databases**: Neo4j (Graph), Vector DB