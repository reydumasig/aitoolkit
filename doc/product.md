# S360 AI Toolkit v1 - Product Documentation

## Overview
S360 AI Toolkit v1 is a multi-assistant platform for operations, HR, and sales/marketing workflows. The current UI focuses on the Ops Assistant and supports multi-file ingestion and document generation.

## Toolkit Modules
### Ops Assistant (current)
- SOP drafting & cleanup
- Process documentation
- Ticket / task summarization

### HR Assistant (planned)
- JD writing
- Interview question generation
- Onboarding checklist creation

### Sales / Marketing Assistant (planned)
- Outreach drafts
- Proposal outlines
- Campaign copy ideation

## Current Capabilities
- Multi-file upload from the web UI
- Document ingestion via API gateway
- SOP or Process document generation
- DOCX export with formatted sections
- Mock AI mode for demos without model quota

## User Flow (Ops Assistant)
1) Upload one or more source files (docx, pdf, txt, xlsx, md)
2) Files are stored in Blob Storage and sent to the AI service for ingestion
3) Generate SOP or Process Document
4) Download formatted DOCX

## Architecture (MVP)
Next.js Web UI
→ Node.js API Gateway
→ Python AI Service (FastAPI)
→ Azure OpenAI (embeddings + chat)
→ Azure AI Search (vector index)
→ Azure Blob Storage

## Environment Configuration
### API
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER`
- `AI_SERVICE_URL`

### AI Service
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_KEY`
- `AZURE_SEARCH_INDEX`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `MOCK_AI=true` to enable mock generation

### Web
- `NEXT_PUBLIC_API_URL`

## Mock Mode
When `MOCK_AI=true`, the AI service returns deterministic SOP/Process JSON and skips Azure Search/OpenAI calls. This is ideal for demos while model quota is pending.

## Limitations (Current)
- No authentication or user management
- No versioning or document history
- No role-based permissions
- No third-party integrations

## Roadmap (Next)
- HR and Sales/Marketing workflows
- Role-based access and sharing
- Approval workflows and versioning
- Native integrations
