"use client";

import { useMemo, useState } from "react";

type SourceRef = {
  docId: string;
  filename: string;
  chunkId: number;
  quote: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4001";

function escapeHtml(str: string) {
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function highlightInText(fullText: string, quote: string) {
  const cleanQuote = (quote || "").trim();
  if (!fullText) return { __html: "" };

  if (cleanQuote.length < 8) {
    return { __html: escapeHtml(fullText) };
  }

  const safeText = escapeHtml(fullText);
  const safeQuote = escapeHtml(cleanQuote);

  const highlighted = safeText.split(safeQuote).join(
    `<mark style="background: #fff3bf; padding: 0 2px; border-radius: 4px;">${safeQuote}</mark>`
  );

  return { __html: highlighted };
}

export function CitationsViewer({ sources = [] }: { sources?: SourceRef[] }) {
  const [open, setOpen] = useState(false);

  const [chunkModalOpen, setChunkModalOpen] = useState(false);
  const [loadingChunk, setLoadingChunk] = useState(false);
  const [chunkData, setChunkData] = useState<any>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);
  const [activeQuote, setActiveQuote] = useState<string>("");

  const [docModalOpen, setDocModalOpen] = useState(false);
  const [docModalDocId, setDocModalDocId] = useState<string>("");
  const [docModalFilename, setDocModalFilename] = useState<string>("");

  const byDoc = useMemo(() => {
    const map = new Map<string, { filename: string; items: SourceRef[] }>();
    for (const s of sources) {
      if (!map.has(s.docId)) {
        map.set(s.docId, { filename: s.filename, items: [] });
      }
      map.get(s.docId)!.items.push(s);
    }
    return Array.from(map.entries()).map(([docId, v]) => ({ docId, ...v }));
  }, [sources]);

  const grouped = useMemo(() => {
    const map = new Map<string, SourceRef[]>();
    for (const s of sources) {
      const key = `${s.filename} (chunk ${s.chunkId})`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(s);
    }
    return Array.from(map.entries());
  }, [sources]);

  const docModalSources = useMemo(() => {
    if (!docModalDocId) return [];
    const found = byDoc.find((d) => d.docId === docModalDocId);
    return found?.items || [];
  }, [byDoc, docModalDocId]);

  const docModalGrouped = useMemo(() => {
    const map = new Map<number, SourceRef[]>();
    for (const s of docModalSources) {
      if (!map.has(s.chunkId)) map.set(s.chunkId, []);
      map.get(s.chunkId)!.push(s);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [docModalSources]);

  async function viewChunk(docId: string, chunkId: number, quote: string) {
    setChunkModalOpen(true);
    setLoadingChunk(true);
    setChunkError(null);
    setChunkData(null);
    setActiveQuote(quote || "");

    try {
      const r = await fetch(
        `${API}/source-chunk?docId=${encodeURIComponent(docId)}&chunkId=${chunkId}`
      );
      const data = await r.json();
      if (!r.ok) throw new Error(data?.error || "Failed to load source chunk");
      setChunkData(data);
    } catch (e: any) {
      setChunkError(e.message || "Failed to load chunk");
    } finally {
      setLoadingChunk(false);
    }
  }

  async function openFullDoc(docId: string) {
    const r = await fetch(`${API}/doc-preview-url?docId=${encodeURIComponent(docId)}`);
    const data = await r.json();
    if (!r.ok) {
      alert(data?.error || "Failed to open document");
      return;
    }
    window.open(data.url, "_blank", "noopener,noreferrer");
  }

  function openDocCitationsModal(docId: string, filename: string) {
    setDocModalDocId(docId);
    setDocModalFilename(filename);
    setDocModalOpen(true);
  }

  if (!sources?.length) {
    return <div style={{ fontSize: 12, opacity: 0.7 }}>No citations provided.</div>;
  }

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          border: "1px solid #ddd",
          background: "#fff",
          padding: "6px 10px",
          borderRadius: 8,
          cursor: "pointer",
          fontSize: 12,
        }}
      >
        {open ? "Hide sources" : `Show sources (${sources.length})`}
      </button>

      {open && (
        <div
          style={{
            marginTop: 8,
            border: "1px solid #eee",
            borderRadius: 10,
            padding: 10,
            background: "#fafafa",
          }}
        >
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            {byDoc.map((d) => (
              <button
                key={d.docId}
                onClick={() => openDocCitationsModal(d.docId, d.filename)}
                style={btn}
                title="View all citations grouped by chunk for this document"
              >
                View all citations: {d.filename}
              </button>
            ))}
          </div>

          {grouped.map(([key, items]) => (
            <div key={key} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 12 }}>{key}</div>

              {items.map((s, idx) => (
                <div
                  key={`${s.docId}-${s.chunkId}-${idx}`}
                  style={{
                    marginTop: 6,
                    padding: 8,
                    borderRadius: 8,
                    border: "1px solid #eee",
                    background: "#fff",
                  }}
                >
                  <div style={{ fontSize: 11, opacity: 0.8 }}>docId: {s.docId}</div>

                  <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.35 }}>
                    “{s.quote}”
                  </div>

                  <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      onClick={() => viewChunk(s.docId, s.chunkId, s.quote)}
                      style={btn}
                    >
                      View source chunk
                    </button>
                    <button
                      onClick={() => openFullDoc(s.docId)}
                      style={btn}
                    >
                      Open full document
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {chunkModalOpen && (
        <div onClick={() => setChunkModalOpen(false)} style={overlay}>
          <div onClick={(e) => e.stopPropagation()} style={modal}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div>
                <div style={{ fontWeight: 700 }}>Source Chunk (Evidence Highlighted)</div>
                {chunkData?.filename ? (
                  <div style={{ fontSize: 12, opacity: 0.8 }}>
                    {chunkData.filename} — chunk {chunkData.chunkId}
                  </div>
                ) : null}
              </div>

              <button onClick={() => setChunkModalOpen(false)} style={btn}>
                Close
              </button>
            </div>

            {activeQuote?.trim() ? (
              <div style={callout}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Evidence used</div>
                <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.35 }}>
                  “{activeQuote}”
                </div>
              </div>
            ) : null}

            <div style={{ marginTop: 12 }}>
              {loadingChunk && <div>Loading…</div>}
              {chunkError && <div style={{ color: "crimson" }}>{chunkError}</div>}

              {chunkData?.content && (
                <div
                  style={chunkBox}
                  dangerouslySetInnerHTML={highlightInText(chunkData.content, activeQuote)}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {docModalOpen && (
        <div onClick={() => setDocModalOpen(false)} style={overlay}>
          <div onClick={(e) => e.stopPropagation()} style={modal}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div>
                <div style={{ fontWeight: 700 }}>All Citations for Document</div>
                <div style={{ fontSize: 12, opacity: 0.8 }}>{docModalFilename}</div>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={() => openFullDoc(docModalDocId)} style={btn}>
                  Open full document
                </button>
                <button onClick={() => setDocModalOpen(false)} style={btn}>
                  Close
                </button>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              {docModalGrouped.length === 0 ? (
                <div style={{ opacity: 0.75 }}>No citations found for this document.</div>
              ) : (
                docModalGrouped.map(([chunkId, items]) => (
                  <div
                    key={chunkId}
                    style={{
                      border: "1px solid #eee",
                      borderRadius: 12,
                      padding: 12,
                      marginBottom: 12,
                      background: "#fafafa",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <div style={{ fontWeight: 700, fontSize: 13 }}>Chunk {chunkId}</div>
                      <button
                        onClick={() => viewChunk(docModalDocId, chunkId, items[0]?.quote || "")}
                        style={btn}
                      >
                        View chunk
                      </button>
                    </div>

                    <div style={{ marginTop: 8 }}>
                      {items.map((s, idx) => (
                        <div
                          key={`${s.docId}-${s.chunkId}-${idx}`}
                          style={{
                            marginTop: 8,
                            padding: 10,
                            borderRadius: 10,
                            border: "1px solid #eee",
                            background: "#fff",
                          }}
                        >
                          <div style={{ fontSize: 13, lineHeight: 1.35 }}>“{s.quote}”</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const btn: any = {
  border: "1px solid #ddd",
  background: "#fff",
  padding: "6px 10px",
  borderRadius: 8,
  cursor: "pointer",
  fontSize: 12,
  height: 32,
};

const overlay: any = {
  position: "fixed",
  inset: 0,
  background: "rgba(0,0,0,0.35)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 16,
  zIndex: 9999,
};

const modal: any = {
  width: "min(920px, 96vw)",
  maxHeight: "85vh",
  overflow: "auto",
  background: "#fff",
  borderRadius: 12,
  border: "1px solid #eee",
  padding: 14,
};

const callout: any = {
  marginTop: 10,
  border: "1px solid #eee",
  borderRadius: 10,
  padding: 10,
  background: "#fafafa",
};

const chunkBox: any = {
  marginTop: 8,
  whiteSpace: "pre-wrap",
  background: "#fafafa",
  border: "1px solid #eee",
  borderRadius: 10,
  padding: 12,
  fontSize: 13,
  lineHeight: 1.45,
  fontFamily:
    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
};
