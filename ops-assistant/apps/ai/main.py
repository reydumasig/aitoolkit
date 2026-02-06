import os, re, json, math
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
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

class GenerateSopRequest(BaseModel):
    docIds: List[str]
    style: str = "standard"

class GenerateProcessRequest(BaseModel):
    docIds: List[str]
    includeRaci: bool = False

# ---------- Utilities ----------
def download_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def extract_text(doc_type: str, b: bytes) -> str:
    doc_type = doc_type.lower()

    if doc_type in ["txt", "md"]:
        return b.decode("utf-8", errors="ignore")

    if doc_type in ["docx"]:
        from io import BytesIO
        f = BytesIO(b)
        d = Document(f)
        return "\n".join([p.text for p in d.paragraphs if p.text.strip()])

    if doc_type in ["pdf"]:
        from io import BytesIO
        f = BytesIO(b)
        reader = PdfReader(f)
        pages = []
        for p in reader.pages:
            t = p.extract_text() or ""
            if t.strip():
                pages.append(t)
        return "\n\n".join(pages)

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
        return "\n".join(chunks)

    # Google Docs exports will typically be docx or pdf; treat unknown as text
    return b.decode("utf-8", errors="ignore")

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

def upsert_chunks(doc_id: str, filename: str, doc_type: str, chunks: List[str]) -> None:
    if not search_client:
        raise HTTPException(500, "Search client not configured")

    embeddings = aoai_embeddings(chunks)

    docs = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        docs.append({
            "id": f"{doc_id}_{idx}",
            "docId": doc_id,
            "filename": filename,
            "docType": doc_type,
            "chunkId": idx,
            "content": chunk,
            "contentVector": emb
        })

    # mergeOrUpload behavior
    search_client.upload_documents(docs)

def retrieve_context(doc_ids: List[str], query: str, k: int = 8) -> str:
    if MOCK_AI:
        return ""
    if not search_client:
        raise HTTPException(500, "Search client not configured")

    qvec = aoai_embeddings([query])[0]

    # Newer SDK uses `vector_queries` naming in some paths; SearchClient supports vector search via kwargs.
    # We'll rely on the SDK's current signature that accepts vector queries.
    results = search_client.search(
        search_text="",
        filter=" or ".join([f"docId eq '{d}'" for d in doc_ids]) if doc_ids else None,
        vector_queries=[{
            "kind": "vector",
            "vector": qvec,
            "k": k,
            "fields": "contentVector"
        }],
        select=["content", "filename", "chunkId", "docId"]
    )

    parts = []
    for r in results:
        parts.append(f"[{r['filename']} | chunk {r['chunkId']}] {r['content']}")
    return "\n\n".join(parts)

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
            {"step": 1, "action": "Collect inputs", "owner": "Analyst", "tools": ["Upload UI"], "output": "Source files"},
            {"step": 2, "action": "Draft SOP", "owner": "Ops Lead", "tools": ["Ops Assistant"], "output": "SOP draft"},
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
            {"step": 1, "what_happens": "Intake request", "owner": "Ops Lead"},
            {"step": 2, "what_happens": "Generate doc", "owner": "Analyst"},
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
    text = extract_text(req.docType, b)
    chunks = chunk_text(text)

    if not chunks:
        raise HTTPException(400, "No extractable text found")

    if not MOCK_AI:
        upsert_chunks(req.docId, req.filename, req.docType, chunks)
    return {"ok": True, "docId": req.docId, "chunks": len(chunks)}

@app.post("/generate/sop")
def generate_sop(req: GenerateSopRequest):
    if MOCK_AI:
        return mock_sop(req.docIds, req.style)
    context = retrieve_context(req.docIds, query="Create an SOP from these meeting notes and documents.")
    system = (
        "You are an operations analyst. Create an SOP with strict JSON output only."
        " No markdown. No extra keys."
    )
    user = f"""
Use the source context to create an SOP.
Return JSON with exactly this schema:
{{
  "title": str,
  "purpose": str,
  "scope": str,
  "roles": [{{"role": str, "responsibilities": [str]}}],
  "prerequisites": [str],
  "steps": [{{"step": int, "action": str, "owner": str, "tools": [str], "output": str}}],
  "exceptions": [str],
  "audit_checklist": [str]
}}

Style: {req.style}

SOURCE CONTEXT:
{context}
"""
    out = aoai_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ])
    try:
        return json.loads(out)
    except Exception:
        raise HTTPException(500, f"Model returned non-JSON output: {out[:300]}")

@app.post("/generate/process")
def generate_process(req: GenerateProcessRequest):
    if MOCK_AI:
        return mock_process(req.docIds, req.includeRaci)
    context = retrieve_context(req.docIds, query="Create a process document from these notes and files.")
    system = (
        "You are an operations analyst. Create a process document with strict JSON output only."
        " No markdown. No extra keys."
    )
    user = f"""
Use the source context to create a Process Document.
Return JSON with exactly this schema:
{{
  "title": str,
  "overview": str,
  "trigger": str,
  "inputs": [str],
  "outputs": [str],
  "systems": [str],
  "process_steps": [{{"step": int, "what_happens": str, "owner": str}}],
  "edge_cases": [str],
  "metrics": [str],
  "raci": [{{"activity": str, "r": str, "a": str, "c": [str], "i": [str]}}]
}}

If includeRaci is false, return raci as an empty list.

includeRaci: {req.includeRaci}

SOURCE CONTEXT:
{context}
"""
    out = aoai_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ])
    try:
        return json.loads(out)
    except Exception:
        raise HTTPException(500, f"Model returned non-JSON output: {out[:300]}")
