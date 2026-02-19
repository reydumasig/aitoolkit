import os, re, json, math
from typing import List, Dict, Any, Optional, Literal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import requests

from docx import Document
from pypdf import PdfReader
import openpyxl

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

app = FastAPI(title="Ops Assistant AI")

# ---------- ENV LOADER ----------
def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

load_env()

# ---------- ENV ----------
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "opsassistant-docs")

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-08-01-preview")
EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
EMB_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT") or AOAI_ENDPOINT
CHAT_ENDPOINT = os.getenv("AZURE_OPENAI_CHAT_ENDPOINT") or AOAI_ENDPOINT
MOCK_AI = os.getenv("MOCK_AI", "false").lower() in ("1", "true", "yes", "y")

if not all([SEARCH_ENDPOINT, SEARCH_KEY, AOAI_ENDPOINT, AOAI_KEY, EMB_DEPLOYMENT, CHAT_DEPLOYMENT]):
    # allow boot without env in early dev, but endpoints will fail
    pass

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX,
    credential=AzureKeyCredential(SEARCH_KEY)
) if SEARCH_ENDPOINT and SEARCH_KEY else None

# ---------- Models ----------
class IngestRequest(BaseModel):
    docId: str
    docType: str
    filename: str
    blobUrl: str
    blobName: str
    authorityLevel: Optional[str] = "standard"

class SourceRef(BaseModel):
    docId: str
    filename: str
    chunkId: int
    quote: str

class GenerateSopRequest(BaseModel):
    docIds: List[str]
    style: str = "standard"

class GenerateProcessRequest(BaseModel):
    docIds: List[str]
    includeRaci: bool = False

class VerifiedSopResponse(BaseModel):
    sop: Dict[str, Any]
    verification: Dict[str, Any]

class SopStep(BaseModel):
    step: int
    action: str
    owner: str
    tools: List[str]
    output: str
    sources: List[SourceRef]

class SopResponse(BaseModel):
    title: str
    purpose: str
    scope: str
    roles: List[Dict[str, Any]]
    prerequisites: List[str]
    steps: List[SopStep]
    exceptions: List[str]
    audit_checklist: List[str]

class ProcessStep(BaseModel):
    step: int
    what_happens: str
    owner: str
    sources: List[SourceRef]

class ProcessResponse(BaseModel):
    title: str
    overview: str
    trigger: str
    inputs: List[str]
    outputs: List[str]
    systems: List[str]
    process_steps: List[ProcessStep]
    edge_cases: List[str]
    metrics: List[str]
    raci: List[Dict[str, Any]]

class VerificationIssue(BaseModel):
    type: Literal["missing_source", "weak_evidence", "conflict", "ambiguous"]
    step: int
    details: str
    recommendation: str

class VerificationConflict(BaseModel):
    topic: str
    sources: List[SourceRef]
    recommendation: str

class VerificationResponse(BaseModel):
    issues: List[VerificationIssue]
    conflicts: List[VerificationConflict]
    missing_info: List[str]
    overall_confidence: Literal["low", "medium", "high"]

# ---------- Utilities ----------
def download_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def extract_chunks(doc_type: str, b: bytes) -> List[Dict[str, Any]]:
    doc_type = doc_type.lower()

    if doc_type in ["txt", "md"]:
        return [{"content": b.decode("utf-8", errors="ignore"), "pageNumber": None, "sectionTitle": None}]

    if doc_type in ["docx"]:
        from io import BytesIO
        f = BytesIO(b)
        d = Document(f)
        chunks = []
        current_title = None
        buffer = []
        for p in d.paragraphs:
            text = (p.text or "").strip()
            if not text:
                continue
            style = (p.style.name or "").lower() if p.style else ""
            if style.startswith("heading"):
                if buffer:
                    chunks.append({
                        "content": "\n".join(buffer),
                        "pageNumber": None,
                        "sectionTitle": current_title,
                    })
                    buffer = []
                current_title = text
            else:
                buffer.append(text)
        if buffer:
            chunks.append({
                "content": "\n".join(buffer),
                "pageNumber": None,
                "sectionTitle": current_title,
            })
        return chunks or [{"content": "", "pageNumber": None, "sectionTitle": None}]

    if doc_type in ["pdf"]:
        from io import BytesIO
        f = BytesIO(b)
        reader = PdfReader(f)
        pages = []
        for idx, p in enumerate(reader.pages):
            t = p.extract_text() or ""
            if t.strip():
                pages.append({
                    "content": t,
                    "pageNumber": idx + 1,
                    "sectionTitle": None,
                })
        return pages or [{"content": "", "pageNumber": None, "sectionTitle": None}]

    if doc_type in ["xlsx"]:
        from io import BytesIO
        f = BytesIO(b)
        wb = openpyxl.load_workbook(f, data_only=True)
        chunks = []
        for ws in wb.worksheets:
            chunks.append(f"Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                line = "\t".join([str(c) for c in row if c is not None])
                if line.strip():
                    chunks.append(line)
        return [{"content": "\n".join(chunks), "pageNumber": None, "sectionTitle": None}]

    # Google Docs exports will typically be docx or pdf; treat unknown as text
    return [{"content": b.decode("utf-8", errors="ignore"), "pageNumber": None, "sectionTitle": None}]

def chunk_text_with_meta(
    chunks: List[Dict[str, Any]],
    max_chars: int = 1800,
    overlap: int = 200
) -> List[Dict[str, Any]]:
    out = []
    for item in chunks:
        text = re.sub(r"\n{3,}", "\n\n", (item.get("content") or "")).strip()
        if not text:
            continue
        i = 0
        while i < len(text):
            end = min(len(text), i + max_chars)
            chunk = text[i:end]
            out.append({
                "content": chunk,
                "pageNumber": item.get("pageNumber"),
                "sectionTitle": item.get("sectionTitle"),
            })
            i = end - overlap
            if i < 0:
                i = 0
            if end == len(text):
                break
    return out

def chunk_text(text: str, max_chars: int = 1800, overlap: int = 200) -> List[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    i = 0
    while i < len(text):
        end = min(len(text), i + max_chars)
        chunk = text[i:end]
        chunks.append(chunk)
        i = end - overlap
        if i < 0: i = 0
        if end == len(text): break
    return chunks

def aoai_embeddings(texts: List[str]) -> List[List[float]]:
    url = f"{EMB_ENDPOINT}/openai/deployments/{EMB_DEPLOYMENT}/embeddings?api-version={AOAI_API_VERSION}"
    headers = {"api-key": AOAI_KEY, "Content-Type": "application/json"}
    payload = {"input": texts}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return [item["embedding"] for item in data["data"]]

def aoai_chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    url = f"{CHAT_ENDPOINT}/openai/deployments/{CHAT_DEPLOYMENT}/chat/completions?api-version={AOAI_API_VERSION}"
    headers = {"api-key": AOAI_KEY, "Content-Type": "application/json"}
    payload = {
        "messages": messages,
        "temperature": temperature
    }
    r = requests.post(url, headers=headers, json=payload, timeout=90)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def upsert_chunks(
    doc_id: str,
    filename: str,
    doc_type: str,
    blob_name: str,
    authority_level: Optional[str],
    chunks: List[Dict[str, Any]]
) -> None:
    if not search_client:
        raise HTTPException(500, "Search client not configured")

    embeddings = aoai_embeddings([c["content"] for c in chunks])

    docs = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        docs.append({
            "id": f"{doc_id}_{idx}",
            "docId": doc_id,
            "filename": filename,
            "docType": doc_type,
            "blobName": blob_name,
            "authorityLevel": authority_level or "standard",
            "chunkId": idx,
            "pageNumber": chunk.get("pageNumber"),
            "sectionTitle": chunk.get("sectionTitle"),
            "content": chunk["content"],
            "contentVector": emb
        })

    # mergeOrUpload behavior
    search_client.upload_documents(docs)

AUTHORITY_PRIORITY = [
    "policy",
    "approved_sop",
    "process_doc",
    "meeting_notes",
    "standard",
    "unknown",
]

def retrieve_chunks(doc_ids: List[str], query: str, k: int = 8) -> List[Dict[str, Any]]:
    if MOCK_AI:
        return []
    if not search_client:
        raise HTTPException(500, "Search client not configured")

    qvec = aoai_embeddings([query])[0]
    base_filter = " or ".join([f"docId eq '{d}'" for d in doc_ids]) if doc_ids else None

    chunks = []
    seen = set()
    remaining = k
    per_tier = max(1, k // max(1, len(AUTHORITY_PRIORITY)))

    for level in AUTHORITY_PRIORITY:
        if remaining <= 0:
            break
        filters = [base_filter] if base_filter else []
        filters.append(f"authorityLevel eq '{level}'")
        tier_filter = " and ".join(filters)

        results = search_client.search(
            search_text="",
            filter=tier_filter,
            vector_queries=[{
                "kind": "vector",
                "vector": qvec,
                "k": min(remaining, per_tier),
                "fields": "contentVector"
            }],
            select=["content", "filename", "chunkId", "docId"]
        )

        for r in results:
            key = f"{r['docId']}_{r['chunkId']}"
            if key in seen:
                continue
            seen.add(key)
            chunks.append({
                "docId": r["docId"],
                "filename": r["filename"],
                "chunkId": int(r["chunkId"]),
                "content": r["content"],
            })
            remaining -= 1
            if remaining <= 0:
                break

    if remaining > 0:
        results = search_client.search(
            search_text="",
            filter=base_filter,
            vector_queries=[{
                "kind": "vector",
                "vector": qvec,
                "k": remaining,
                "fields": "contentVector"
            }],
            select=["content", "filename", "chunkId", "docId"]
        )
        for r in results:
            key = f"{r['docId']}_{r['chunkId']}"
            if key in seen:
                continue
            seen.add(key)
            chunks.append({
                "docId": r["docId"],
                "filename": r["filename"],
                "chunkId": int(r["chunkId"]),
                "content": r["content"],
            })

    return chunks

def format_context(chunks: List[Dict[str, Any]]) -> str:
    # Include stable citation anchors the model can reference.
    parts = []
    for c in chunks:
        parts.append(
            f"[docId={c['docId']}|file={c['filename']}|chunkId={c['chunkId']}]\n{c['content']}"
        )
    return "\n\n---\n\n".join(parts)

def validate_model(model_cls, data: Any):
    try:
        if hasattr(model_cls, "model_validate"):
            return model_cls.model_validate(data)
        return model_cls.parse_obj(data)
    except Exception as e:
        raise HTTPException(500, f"Model returned invalid schema: {str(e)}")

def mock_sop(doc_ids: List[str], style: str) -> Dict[str, Any]:
    return {
        "title": f"Mock SOP ({style})",
        "purpose": "Demonstrate SOP output without AI connectivity.",
        "scope": "Demo scope for uploaded documents.",
        "roles": [
            {"role": "Ops Lead", "responsibilities": ["Review inputs", "Approve SOP"]},
            {"role": "Analyst", "responsibilities": ["Compile steps", "Validate sources"]},
        ],
        "prerequisites": ["Uploaded source files", "Basic process context"],
        "steps": [
            {
                "step": 1,
                "action": "Collect inputs",
                "owner": "Analyst",
                "tools": ["Upload UI"],
                "output": "Source files",
                "sources": [
                    {
                        "docId": doc_ids[0] if doc_ids else "mock-doc",
                        "filename": "mock-file.txt",
                        "chunkId": 1,
                        "quote": "Inputs were collected from source materials.",
                    }
                ],
            },
            {
                "step": 2,
                "action": "Draft SOP",
                "owner": "Ops Lead",
                "tools": ["Ops Assistant"],
                "output": "SOP draft",
                "sources": [
                    {
                        "docId": doc_ids[0] if doc_ids else "mock-doc",
                        "filename": "mock-file.txt",
                        "chunkId": 2,
                        "quote": "Draft SOP created for review.",
                    }
                ],
            },
        ],
        "exceptions": ["Missing inputs", "Unclear ownership"],
        "audit_checklist": ["All steps have owners", "Outputs match inputs"],
        "docIds": doc_ids,
    }

def mock_process(doc_ids: List[str], include_raci: bool) -> Dict[str, Any]:
    return {
        "title": "Mock Process Doc",
        "overview": "Demonstrate process output without AI connectivity.",
        "trigger": "New request received",
        "inputs": ["Request form", "Source files"],
        "outputs": ["Approved SOP", "Process doc"],
        "systems": ["Ops Assistant"],
        "process_steps": [
            {
                "step": 1,
                "what_happens": "Intake request",
                "owner": "Ops Lead",
                "sources": [
                    {
                        "docId": doc_ids[0] if doc_ids else "mock-doc",
                        "filename": "mock-file.txt",
                        "chunkId": 1,
                        "quote": "Request intake is initiated by Ops Lead.",
                    }
                ],
            },
            {
                "step": 2,
                "what_happens": "Generate doc",
                "owner": "Analyst",
                "sources": [
                    {
                        "docId": doc_ids[0] if doc_ids else "mock-doc",
                        "filename": "mock-file.txt",
                        "chunkId": 2,
                        "quote": "Documentation is generated after intake.",
                    }
                ],
            },
        ],
        "edge_cases": ["Missing data"],
        "metrics": ["Time to draft", "Approval rate"],
        "raci": [] if not include_raci else [
            {"activity": "Draft SOP", "r": "Analyst", "a": "Ops Lead", "c": ["SME"], "i": ["Stakeholders"]},
        ],
        "docIds": doc_ids,
    }

# ---------- Routes ----------
@app.post("/ingest")
def ingest(req: IngestRequest):
    b = download_bytes(req.blobUrl)
    extracted = extract_chunks(req.docType, b)
    chunks = chunk_text_with_meta(extracted)

    if not chunks:
        raise HTTPException(400, "No extractable text found")

    if not MOCK_AI:
        upsert_chunks(
            req.docId,
            req.filename,
            req.docType,
            req.blobName,
            req.authorityLevel,
            chunks
        )
    return {"ok": True, "docId": req.docId, "chunks": len(chunks)}

@app.post("/generate/sop")
def generate_sop(req: GenerateSopRequest):
    if MOCK_AI:
        mock = mock_sop(req.docIds, req.style)
        validated = validate_model(SopResponse, mock)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    chunks = retrieve_chunks(
        req.docIds,
        query="Create an SOP from these meeting notes and documents. Focus on factual steps, owners, tools, and outputs."
    )
    context = format_context(chunks)

    system = (
        "You are an operations analyst. You MUST ground your output in the provided SOURCE CONTEXT.\n"
        "You MUST NOT invent steps. If information is missing, write it as 'Unknown' or add it to exceptions/missing info.\n"
        "Return STRICT JSON ONLY. No markdown. No extra keys.\n"
        "Every step MUST include at least one source reference taken from the SOURCE CONTEXT anchors.\n"
        "Each source must include a short direct quote (<=25 words) copied from the context."
    )

    user = f"""
Create an SOP using ONLY the SOURCE CONTEXT.

Return JSON with EXACTLY this schema:
{{
  "title": str,
  "purpose": str,
  "scope": str,
  "roles": [{{"role": str, "responsibilities": [str]}}],
  "prerequisites": [str],
  "steps": [{{"step": int, "action": str, "owner": str, "tools": [str], "output": str, "sources": [{{"docId": str, "filename": str, "chunkId": int, "quote": str}}]}}],
  "exceptions": [str],
  "audit_checklist": [str]
}}

Rules:
- steps[].sources must reference anchors from SOURCE CONTEXT (docId, filename, chunkId must match).
- quote must be a short exact excerpt from that chunk that supports the step.
- If owner/tool/output is not stated, set it to "Unknown" and cite the closest supporting text.

Style: {req.style}

SOURCE CONTEXT:
{context}
"""

    out = aoai_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], temperature=0.1)
    try:
        parsed = json.loads(out)
        validated = validate_model(SopResponse, parsed)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    except Exception:
        raise HTTPException(500, f"Model returned non-JSON output: {out[:300]}")

@app.post("/generate/process_verified")
def generate_process_verified(req: GenerateProcessRequest):
    if MOCK_AI:
        return {
            "process": mock_process(req.docIds, req.includeRaci),
            "verification": {
                "issues": [],
                "conflicts": [],
                "missing_info": [],
                "overall_confidence": "low"
            },
        }

    process_doc = generate_process(req)

    chunks = retrieve_chunks(
        req.docIds,
        query="Verify process steps against these documents. Identify missing evidence, conflicts, and ambiguous steps."
    )
    context = format_context(chunks)

    verifier_system = (
        "You are a strict QA auditor.\n"
        "Your job: verify each process step is supported by its cited sources.\n"
        "Return STRICT JSON ONLY. No markdown."
    )

    verifier_user = f"""
You will be given:
1) SOURCE CONTEXT
2) A generated Process Document JSON

Tasks:
- For each process step, check if the cited quotes support what_happens and owner.
- Flag steps with missing/weak evidence.
- Flag conflicts if different sources imply different instructions.
- Identify missing information that prevents accuracy.

Return JSON with EXACTLY this schema:
{{
  "issues": [
    {{
      "type": "missing_source" | "weak_evidence" | "conflict" | "ambiguous",
      "step": int,
      "details": str,
      "recommendation": str
    }}
  ],
  "conflicts": [
    {{
      "topic": str,
      "sources": [{{"docId": str, "filename": str, "chunkId": int, "quote": str}}],
      "recommendation": str
    }}
  ],
  "missing_info": [str],
  "overall_confidence": "low" | "medium" | "high"
}}

PROCESS DOC JSON:
{json.dumps(process_doc)}

SOURCE CONTEXT:
{context}
"""

    verification_out = aoai_chat([
        {"role": "system", "content": verifier_system},
        {"role": "user", "content": verifier_user}
    ], temperature=0.0)

    try:
        verification = json.loads(verification_out)
        verification = validate_model(VerificationResponse, verification)
        verification = verification.model_dump() if hasattr(verification, "model_dump") else verification.dict()
    except Exception:
        raise HTTPException(500, f"Verifier returned non-JSON output: {verification_out[:300]}")

    return {
        "process": process_doc,
        "verification": verification
    }

@app.get("/source-chunk")
def source_chunk(docId: str, chunkId: int):
    if MOCK_AI:
        return {
            "docId": docId,
            "filename": "mock-file.txt",
            "chunkId": chunkId,
            "content": "Mock source chunk content for demo highlighting.",
        }
    if not search_client:
        raise HTTPException(500, "Search client not configured")
    try:
        doc = search_client.get_document(key=f"{docId}_{chunkId}")
    except Exception:
        raise HTTPException(404, "Source chunk not found")

    return {
        "docId": doc.get("docId"),
        "filename": doc.get("filename"),
        "chunkId": doc.get("chunkId"),
        "content": doc.get("content"),
    }

@app.get("/doc-meta")
def get_doc_meta(docId: str = Query(...)):
    """
    Returns metadata (blobName, filename, docType) for a given docId.
    We query one chunk and reuse its metadata.
    """
    if not search_client:
        raise HTTPException(500, "Search client not configured")

    results = search_client.search(
        search_text="",
        filter=f"docId eq '{docId}'",
        select=["docId", "filename", "docType", "blobName", "chunkId"],
        top=1
    )

    first = None
    for r in results:
        first = r
        break

    if not first:
        raise HTTPException(404, f"No document found for docId={docId}")

    return {
        "docId": first.get("docId"),
        "filename": first.get("filename"),
        "docType": first.get("docType"),
        "blobName": first.get("blobName")
    }

@app.post("/generate/sop_verified")
def generate_sop_verified(req: GenerateSopRequest):
    if MOCK_AI:
        return {
            "sop": mock_sop(req.docIds, req.style),
            "verification": {
                "issues": [],
                "conflicts": [],
                "missing_info": [],
                "overall_confidence": "low"
            },
        }

    sop = generate_sop(req)

    chunks = retrieve_chunks(
        req.docIds,
        query="Verify SOP steps against these documents. Identify missing evidence, conflicts, and ambiguous steps."
    )
    context = format_context(chunks)

    verifier_system = (
        "You are a strict QA auditor.\n"
        "Your job: verify each SOP step is supported by its cited sources.\n"
        "Return STRICT JSON ONLY. No markdown."
    )

    verifier_user = f"""
You will be given:
1) SOURCE CONTEXT
2) A generated SOP JSON

Tasks:
- For each step, check if the cited quotes actually support the step action/owner/tool/output.
- Flag steps with missing/weak evidence.
- Flag conflicts if different sources imply different instructions.
- Identify missing information that prevents accuracy.

Return JSON with EXACTLY this schema:
{{
  "issues": [
    {{
      "type": "missing_source" | "weak_evidence" | "conflict" | "ambiguous",
      "step": int,
      "details": str,
      "recommendation": str
    }}
  ],
  "conflicts": [
    {{
      "topic": str,
      "sources": [{{"docId": str, "filename": str, "chunkId": int, "quote": str}}],
      "recommendation": str
    }}
  ],
  "missing_info": [str],
  "overall_confidence": "low" | "medium" | "high"
}}

SOP JSON:
{json.dumps(sop)}

SOURCE CONTEXT:
{context}
"""

    verification_out = aoai_chat([
        {"role": "system", "content": verifier_system},
        {"role": "user", "content": verifier_user}
    ], temperature=0.0)

    try:
        verification = json.loads(verification_out)
        verification = validate_model(VerificationResponse, verification)
        verification = verification.model_dump() if hasattr(verification, "model_dump") else verification.dict()
    except Exception:
        raise HTTPException(500, f"Verifier returned non-JSON output: {verification_out[:300]}")

    return {
        "sop": sop,
        "verification": verification
    }

@app.post("/generate/process")
def generate_process(req: GenerateProcessRequest):
    if MOCK_AI:
        mock = mock_process(req.docIds, req.includeRaci)
        validated = validate_model(ProcessResponse, mock)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    chunks = retrieve_chunks(
        req.docIds,
        query="Create a process document from these notes and files. Focus on triggers, inputs/outputs, systems, steps, owners, and exceptions."
    )
    context = format_context(chunks)
    system = (
        "You are an operations analyst. You MUST ground your output in the provided SOURCE CONTEXT.\n"
        "You MUST NOT invent steps. If information is missing, write 'Unknown' or add it to edge_cases/missing info.\n"
        "Return STRICT JSON ONLY. No markdown. No extra keys.\n"
        "Every process step MUST include at least one source reference taken from the SOURCE CONTEXT anchors.\n"
        "Each source must include a short direct quote (<=25 words) copied from the context."
    )
    user = f"""
Create a Process Document using ONLY the SOURCE CONTEXT.
Return JSON with exactly this schema:
{{
  "title": str,
  "overview": str,
  "trigger": str,
  "inputs": [str],
  "outputs": [str],
  "systems": [str],
  "process_steps": [{{"step": int, "what_happens": str, "owner": str, "sources": [{{"docId": str, "filename": str, "chunkId": int, "quote": str}}]}}],
  "edge_cases": [str],
  "metrics": [str],
  "raci": [{{"activity": str, "r": str, "a": str, "c": [str], "i": [str]}}]
}}

Rules:
- process_steps[].sources must reference anchors from SOURCE CONTEXT (docId, filename, chunkId must match).
- quote must be a short exact excerpt from that chunk that supports the step.
- If owner is not stated, set owner to "Unknown" and cite the closest supporting text.

If includeRaci is false, return raci as an empty list.

includeRaci: {req.includeRaci}

SOURCE CONTEXT:
{context}
"""
    out = aoai_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], temperature=0.1)
    try:
        parsed = json.loads(out)
        validated = validate_model(ProcessResponse, parsed)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    except Exception:
        raise HTTPException(500, f"Model returned non-JSON output: {out[:300]}")
