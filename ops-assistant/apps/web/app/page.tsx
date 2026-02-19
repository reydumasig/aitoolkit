"use client";

import { useState } from "react";
import { Document, Packer, Paragraph, TextRun } from "docx";
import { SopViewer } from "./components/SopViewer";
import { ProcessViewer } from "./components/ProcessViewer";
import { VerificationPanel } from "./components/VerificationPanel";
import {
  Alert,
  Box,
  Button,
  Container,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4001";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [docIds, setDocIds] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [mode, setMode] = useState<"sop" | "process" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  async function upload() {
    if (!files.length) return;
    setError(null);
    setIsUploading(true);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    try {
      const r = await fetch(`${API}/upload`, { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) {
        setError(data?.error || "Upload failed");
        return;
      }
      const items = Array.isArray(data?.items) ? data.items : data?.docId ? [data] : [];
      const errs = Array.isArray(data?.errors) ? data.errors : [];
      setDocIds((prev) => [...prev, ...items.map((i: any) => i.docId)]);
      setResult(null);
      setFiles([]);
      if (errs.length) {
        setError(`Some files failed: ${errs.map((e: any) => e.filename).join(", ")}`);
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function genSop() {
    setError(null);
    setIsGenerating(true);
    setMode("sop");
    const r = await fetch(`${API}/generate/sop_verified`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ docIds, style: "standard" }),
    });
    try {
      const data = await r.json();
      if (!r.ok) {
        setError(data?.error || "Generate SOP failed");
        return;
      }
      setResult(data);
    } finally {
      setIsGenerating(false);
    }
  }

  async function genProcess() {
    setError(null);
    setIsGenerating(true);
    setMode("process");
    const r = await fetch(`${API}/generate/process_verified`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ docIds, includeRaci: false }),
    });
    try {
      const data = await r.json();
      if (!r.ok) {
        setError(data?.error || "Generate Process failed");
        return;
      }
      setResult(data);
    } finally {
      setIsGenerating(false);
    }
  }

  function para(text: string, opts?: { bold?: boolean }) {
    return new Paragraph({
      children: [new TextRun({ text, bold: opts?.bold })],
    });
  }

  function heading(text: string) {
    return new Paragraph({ text, heading: "Heading2" });
  }

  function list(items: string[]) {
    return items.map((item) => new Paragraph({ text: item, bullet: { level: 0 } }));
  }

  function formatSop(doc: any) {
    const children: Paragraph[] = [];
    children.push(new Paragraph({ text: doc.title || "SOP", heading: "Heading1" }));
    if (doc.purpose) children.push(heading("Purpose"), para(doc.purpose));
    if (doc.scope) children.push(heading("Scope"), para(doc.scope));
    if (doc.roles?.length) {
      children.push(heading("Roles & Responsibilities"));
      doc.roles.forEach((r: any) => {
        const title = r.role ? `${r.role}:` : "Role:";
        children.push(para(title, { bold: true }));
        if (Array.isArray(r.responsibilities)) {
          children.push(...list(r.responsibilities));
        }
      });
    }
    if (Array.isArray(doc.prerequisites) && doc.prerequisites.length) {
      children.push(heading("Prerequisites"), ...list(doc.prerequisites));
    }
    if (Array.isArray(doc.steps) && doc.steps.length) {
      children.push(heading("Steps"));
      doc.steps.forEach((s: any) => {
        const line = `Step ${s.step ?? ""}: ${s.action ?? ""}`.trim();
        children.push(para(line, { bold: true }));
        if (s.owner) children.push(para(`Owner: ${s.owner}`));
        if (Array.isArray(s.tools) && s.tools.length) {
          children.push(para(`Tools: ${s.tools.join(", ")}`));
        }
        if (s.output) children.push(para(`Output: ${s.output}`));
        if (Array.isArray(s.sources) && s.sources.length) {
          children.push(para("Sources:", { bold: true }));
          s.sources.forEach((src: any) => {
            const ref = `[${src.filename || "file"} | chunk ${src.chunkId ?? "?"}] ${src.quote || ""}`.trim();
            children.push(para(ref));
          });
        }
      });
    }
    if (Array.isArray(doc.exceptions) && doc.exceptions.length) {
      children.push(heading("Exceptions"), ...list(doc.exceptions));
    }
    if (Array.isArray(doc.audit_checklist) && doc.audit_checklist.length) {
      children.push(heading("Audit Checklist"), ...list(doc.audit_checklist));
    }
    return children;
  }

  function formatProcess(doc: any) {
    const children: Paragraph[] = [];
    children.push(new Paragraph({ text: doc.title || "Process Document", heading: "Heading1" }));
    if (doc.overview) children.push(heading("Overview"), para(doc.overview));
    if (doc.trigger) children.push(heading("Trigger"), para(doc.trigger));
    if (Array.isArray(doc.inputs) && doc.inputs.length) {
      children.push(heading("Inputs"), ...list(doc.inputs));
    }
    if (Array.isArray(doc.outputs) && doc.outputs.length) {
      children.push(heading("Outputs"), ...list(doc.outputs));
    }
    if (Array.isArray(doc.systems) && doc.systems.length) {
      children.push(heading("Systems"), ...list(doc.systems));
    }
    if (Array.isArray(doc.process_steps) && doc.process_steps.length) {
      children.push(heading("Process Steps"));
      doc.process_steps.forEach((s: any) => {
        const line = `Step ${s.step ?? ""}: ${s.what_happens ?? ""}`.trim();
        children.push(para(line, { bold: true }));
        if (s.owner) children.push(para(`Owner: ${s.owner}`));
        if (Array.isArray(s.sources) && s.sources.length) {
          children.push(para("Sources:", { bold: true }));
          s.sources.forEach((src: any) => {
            const ref = `[${src.filename || "file"} | chunk ${src.chunkId ?? "?"}] ${src.quote || ""}`.trim();
            children.push(para(ref));
          });
        }
      });
    }
    if (Array.isArray(doc.edge_cases) && doc.edge_cases.length) {
      children.push(heading("Edge Cases"), ...list(doc.edge_cases));
    }
    if (Array.isArray(doc.metrics) && doc.metrics.length) {
      children.push(heading("Metrics"), ...list(doc.metrics));
    }
    if (Array.isArray(doc.raci) && doc.raci.length) {
      children.push(heading("RACI"));
      doc.raci.forEach((r: any) => {
        const line = r.activity ? `Activity: ${r.activity}` : "Activity:";
        children.push(para(line, { bold: true }));
        if (r.r) children.push(para(`R: ${r.r}`));
        if (r.a) children.push(para(`A: ${r.a}`));
        if (Array.isArray(r.c) && r.c.length) children.push(para(`C: ${r.c.join(", ")}`));
        if (Array.isArray(r.i) && r.i.length) children.push(para(`I: ${r.i.join(", ")}`));
      });
    }
    return children;
  }

  async function downloadDocx() {
    const docData = mode === "sop" ? result?.sop : result?.process;
    if (!docData) return;
    const title = docData?.title || "Ops Assistant Output";
    const isSop = mode === "sop";
    const children = isSop ? formatSop(docData) : formatProcess(docData);
    const doc = new Document({
      sections: [
        {
          children: children.length ? children : [para(title, { bold: true })],
        },
      ],
    });
    const blob = await Packer.toBlob(doc);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[^a-z0-9-_]+/gi, "_").toLowerCase()}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copyJson() {
    if (!result) return;
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
  }

  return (
    <Box sx={{ bgcolor: "grey.50", minHeight: "100vh" }}>
      <Box sx={{ display: "flex", minHeight: "100vh" }}>
        <Box
          component="aside"
          sx={{
            width: 280,
            bgcolor: "common.white",
            borderRight: "1px solid",
            borderColor: "divider",
            p: 3,
          }}
        >
          <Typography variant="h6" fontWeight={700}>
            S360 AI Toolkit v1
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Core assistants
          </Typography>

          <Stack spacing={2} sx={{ mt: 3 }}>
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                Ops Assistant
              </Typography>
              <Typography variant="body2" color="text.secondary">
                SOP drafting & cleanup
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Process documentation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ticket / task summarization
              </Typography>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                HR Assistant
              </Typography>
              <Typography variant="body2" color="text.secondary">
                JD writing
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Interview question generation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Onboarding checklist creation
              </Typography>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                Sales / Marketing Assistant
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Outreach drafts
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Proposal outlines
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Campaign copy ideation
              </Typography>
            </Box>
          </Stack>
        </Box>

        <Box sx={{ flex: 1, py: 6 }}>
          <Container maxWidth="md">
            <Stack spacing={3}>
              <Box>
                <Typography variant="h4" fontWeight={700}>
                  Ops Assistant
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Upload source files, then generate SOP or process docs.
                </Typography>
              </Box>

              {error && <Alert severity="error">{error}</Alert>}

              <Paper variant="outlined" sx={{ p: 3 }}>
                <Stack spacing={2}>
                  <Typography variant="h6">Upload source files</Typography>
                  <Stack direction="row" spacing={2} alignItems="center">
                    <TextField
                      type="file"
                      inputProps={{ accept: ".docx,.pdf,.txt,.xlsx,.md", multiple: true }}
                      onChange={(e) => setFiles(Array.from(e.target.files || []))}
                    />
                    <Button
                      variant="contained"
                      onClick={upload}
                      disabled={!files.length || isUploading}
                    >
                      {isUploading ? "Uploading..." : "Upload"}
                    </Button>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    Selected files: {files.length ? files.map((f) => f.name).join(", ") : "(none)"}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Loaded docIds: {docIds.join(", ") || "(none)"}
                  </Typography>
                </Stack>
              </Paper>

              <Stack direction="row" spacing={2} alignItems="center">
                <Button variant="contained" onClick={genSop} disabled={!docIds.length || isGenerating}>
                  Generate SOP (Verified)
                </Button>
                <Button variant="outlined" onClick={genProcess} disabled={!docIds.length || isGenerating}>
                  Generate Process (Verified)
                </Button>
                <Button variant="text" onClick={copyJson} disabled={!result}>
                  Copy JSON
                </Button>
              </Stack>

              {result?.verification && (
                <Paper variant="outlined" sx={{ p: 3 }}>
                  <VerificationPanel verification={result.verification} />
                </Paper>
              )}

              <Paper variant="outlined" sx={{ p: 3 }}>
                <Stack spacing={1}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">Output</Typography>
                    <Button variant="outlined" onClick={downloadDocx} disabled={!result}>
                      Download DOCX
                    </Button>
                  </Stack>
                  {mode === "sop" && result?.sop ? <SopViewer sop={result.sop} /> : null}
                  {mode === "process" && result?.process ? (
                    <ProcessViewer process={result.process} />
                  ) : null}
                  {!result && (
                    <Typography variant="body2" color="text.secondary">
                      Upload docs, then generate a Verified SOP or Process Doc.
                    </Typography>
                  )}
                  <Box
                    component="pre"
                    sx={{
                      whiteSpace: "pre-wrap",
                      bgcolor: "grey.100",
                      p: 2,
                      borderRadius: 1,
                      m: 0,
                      minHeight: 160,
                    }}
                  >
                    {result ? JSON.stringify(result, null, 2) : "No output yet."}
                  </Box>
                </Stack>
              </Paper>
            </Stack>
          </Container>
        </Box>
      </Box>
    </Box>
  );
}
