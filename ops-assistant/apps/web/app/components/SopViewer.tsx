"use client";

import { CitationsViewer } from "./CitationsViewer";

export function SopViewer({ sop }: { sop: any }) {
  if (!sop) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <h2 style={{ marginBottom: 6 }}>{sop.title || "Untitled SOP"}</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>{sop.purpose}</p>

      <Section title="Scope" text={sop.scope} />

      <Section title="Roles">
        {(sop.roles || []).map((r: any, idx: number) => (
          <div key={idx} style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600 }}>{r.role}</div>
            <ul style={{ marginTop: 6 }}>
              {(r.responsibilities || []).map((x: string, i: number) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        ))}
      </Section>

      <Section title="Prerequisites">
        <ul>
          {(sop.prerequisites || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>

      <Section title="Steps">
        {(sop.steps || []).map((s: any) => (
          <div
            key={s.step}
            style={{
              border: "1px solid #eee",
              borderRadius: 12,
              padding: 12,
              marginBottom: 12,
              background: "#fff",
            }}
          >
            <div style={{ fontWeight: 700 }}>
              Step {s.step}: {s.action}
            </div>
            <div style={{ marginTop: 6, fontSize: 13, opacity: 0.85 }}>
              <div>
                <b>Owner:</b> {s.owner}
              </div>
              <div>
                <b>Tools:</b> {(s.tools || []).join(", ") || "—"}
              </div>
              <div>
                <b>Output:</b> {s.output || "—"}
              </div>
            </div>

            <CitationsViewer sources={s.sources || []} />
          </div>
        ))}
      </Section>

      <Section title="Exceptions">
        <ul>
          {(sop.exceptions || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>

      <Section title="Audit Checklist">
        <ul>
          {(sop.audit_checklist || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function Section({
  title,
  text,
  children,
}: {
  title: string;
  text?: string;
  children?: any;
}) {
  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ marginBottom: 6 }}>{title}</h3>
      {text ? <div style={{ opacity: 0.9 }}>{text}</div> : null}
      {children}
    </div>
  );
}
