"use client";

import { CitationsViewer } from "./CitationsViewer";

export function ProcessViewer({ process }: { process: any }) {
  if (!process) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <h2 style={{ marginBottom: 6 }}>{process.title || "Untitled Process"}</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>{process.overview}</p>

      <Section title="Trigger" text={process.trigger} />

      <TwoCol
        leftTitle="Inputs"
        leftItems={process.inputs || []}
        rightTitle="Outputs"
        rightItems={process.outputs || []}
      />

      <Section title="Systems">
        <ul>
          {(process.systems || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>

      <Section title="Process Steps">
        {(process.process_steps || []).map((s: any) => (
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
              Step {s.step}: {s.what_happens}
            </div>
            <div style={{ marginTop: 6, fontSize: 13, opacity: 0.85 }}>
              <b>Owner:</b> {s.owner}
            </div>

            <CitationsViewer sources={s.sources || []} />
          </div>
        ))}
      </Section>

      <Section title="Edge Cases">
        <ul>
          {(process.edge_cases || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>

      <Section title="Metrics">
        <ul>
          {(process.metrics || []).map((x: string, i: number) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Section>

      {(process.raci || []).length > 0 && (
        <Section title="RACI (Optional)">
          <div style={{ border: "1px solid #eee", borderRadius: 12, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#fafafa" }}>
                  <th style={th}>Activity</th>
                  <th style={th}>R</th>
                  <th style={th}>A</th>
                  <th style={th}>C</th>
                  <th style={th}>I</th>
                </tr>
              </thead>
              <tbody>
                {(process.raci || []).map((r: any, i: number) => (
                  <tr key={i}>
                    <td style={td}>{r.activity}</td>
                    <td style={td}>{r.r}</td>
                    <td style={td}>{r.a}</td>
                    <td style={td}>{(r.c || []).join(", ")}</td>
                    <td style={td}>{(r.i || []).join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}

const th: any = { textAlign: "left", padding: 10, borderBottom: "1px solid #eee", fontSize: 13 };
const td: any = { padding: 10, borderBottom: "1px solid #eee", fontSize: 13 };

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

function TwoCol({
  leftTitle,
  leftItems,
  rightTitle,
  rightItems,
}: {
  leftTitle: string;
  leftItems: string[];
  rightTitle: string;
  rightItems: string[];
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
      <div>
        <h3 style={{ marginBottom: 6 }}>{leftTitle}</h3>
        <ul>
          {leftItems.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3 style={{ marginBottom: 6 }}>{rightTitle}</h3>
        <ul>
          {rightItems.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
