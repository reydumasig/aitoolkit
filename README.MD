# Ops Assistant (MVP)

Ops Assistant is an AI-powered operations documentation tool designed to turn raw operational inputs—meeting notes, documents, and spreadsheets—into clear, structured SOPs and process documentation.

This repository contains the MVP implementation built with **Next.js**, **Node.js**, **Python**, and **Azure-native AI services**.

---

## 🚀 What This Is

Ops Assistant helps operations teams:
- Generate SOPs from meeting notes and working documents
- Create structured process documentation automatically
- Reduce time spent manually drafting and cleaning ops docs
- Ground outputs in real source materials using RAG (Retrieval-Augmented Generation)

This is **not a chatbot**.  
It is an **AI ops analyst** focused on documentation quality, structure, and reusability.

---

## 🎯 MVP Goals

The MVP focuses on a narrow, high-impact use case:

- Upload operational source files
- Ingest and index content
- Generate SOPs and process docs grounded in uploaded data
- Deliver outputs that are immediately usable with minimal editing

The goal is **speed, clarity, and validation**, not feature completeness.

---

## 🧩 Supported Inputs (MVP)

- `.docx`
- `.txt`
- `.pdf`
- Google Docs exports (docx / pdf)
- `.xlsx` (Excel)

---

## ✨ Core Features (MVP)

### 1. Document Upload & Ingestion
- Upload files via web UI
- Store files in Azure Blob Storage
- Extract and normalize text
- Chunk and embed content
- Index content in Azure AI Search

---

### 2. SOP Generation
Generate a full Standard Operating Procedure from uploaded materials.

**Output structure includes:**
- Title
- Purpose
- Scope
- Roles & responsibilities
- Prerequisites
- Step-by-step actions
- Exceptions
- Audit checklist

Outputs are returned as **strict JSON** for easy rendering and export.

---

### 3. Process Documentation
Generate an end-to-end process document describing how work flows.

**Includes:**
- Overview and trigger
- Inputs and outputs
- Systems involved
- Process steps
- Edge cases
- Metrics
- Optional RACI (disabled by default in MVP)

---

### 4. Retrieval-Augmented Generation (RAG)
- Only uses uploaded documents as context
- Reduces hallucinations
- Supports multi-document reasoning

---

### 5. Simple UI & Export
- Upload interface
- Generate SOP / Process buttons
- JSON output viewer
- Copy outputs for use in Docs, Notion, or Confluence

---

## 🚫 Out of Scope (Intentional)

The following are **not included** in the MVP:
- Authentication or user management
- Permissions or approvals
- Versioning
- Native third-party integrations
- Automation workflows
- Analytics or dashboards

These will be addressed after MVP validation.

---

## 🏗️ Architecture Overview
```
Next.js Web UI
↓
Node.js API Gateway
↓
Python AI Service (FastAPI)
↓
Azure OpenAI (Generation + Embeddings)
↓
Azure AI Search (Vector Index)
↓
Azure Blob Storage (Source Files)
```

---

## 🧠 Model Strategy

### MVP
- Azure OpenAI for:
  - Embeddings
  - Text generation

### Future
- Fine-tuned models on ops documentation
- Hosted open-source models via Azure ML
- Gradual transition toward proprietary LLM ownership

---

## 🛠️ Tech Stack

### Frontend
- Next.js (App Router)
- TypeScript

### API Gateway
- Node.js
- Express
- Multer (file uploads)
- Axios

### AI & Processing
- Python
- FastAPI
- Retrieval-Augmented Generation (RAG)

### Azure Services
- Azure Blob Storage
- Azure AI Search (vector search)
- Azure OpenAI / Microsoft Foundry Models

### Document Parsing
- `python-docx` (DOCX)
- `pypdf` (PDF)
- `openpyxl` (Excel)

---

## 📂 Repository Structure
```
ops-assistant/
├── apps/
│   ├── web/        # Next.js frontend
│   ├── api/        # Node.js API gateway
│   └── ai/         # Python FastAPI AI service
├── README.MD
```

---

## ✅ MVP Success Criteria

- SOP or Process Doc generated in under 5 minutes
- Outputs are structured, readable, and reusable
- Minimal manual editing required
- Clear improvement over manual documentation workflows

---

## 🔮 Future Roadmap (Post-MVP)

- Versioned SOPs and process docs
- Role-based views
- Approval workflows
- Native integrations (Monday, Google Docs, SharePoint)
- Automated updates from new meetings
- Ops knowledge graph
- Team-specific AI assistants

---

## 🧭 Positioning

Ops Assistant is built to convert **operational chaos into structured assets**.

This MVP establishes the foundation for a broader AI-powered operations platform focused on documentation, clarity, and execution.

---