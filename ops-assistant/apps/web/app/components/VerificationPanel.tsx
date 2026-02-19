"use client";

export function VerificationPanel({ verification }: { verification?: any }) {
  if (!verification) return null;

  const issues = verification.issues || [];
  const conflicts = verification.conflicts || [];
  const missing = verification.missing_info || [];
  const confidence = verification.overall_confidence || "unknown";

  const badgeBg =
    confidence === "high" ? "#e6ffed" : confidence === "medium" ? "#fff7e6" : "#ffe6e6";
  const badgeBorder =
    confidence === "high" ? "#b7eb8f" : confidence === "medium" ? "#ffd591" : "#ffa39e";

  return (
    <div style={{ marginTop: 16, border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h3 style={{ margin: 0 }}>Verification</h3>
        <span
          style={{
            fontSize: 12,
            padding: "3px 8px",
            borderRadius: 999,
            background: badgeBg,
            border: `1px solid ${badgeBorder}`,
          }}
        >
          Confidence: {confidence}
        </span>
      </div>

      {issues.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 600 }}>Issues</div>
          <ul style={{ marginTop: 6 }}>
            {issues.map((it: any, idx: number) => (
              <li key={idx} style={{ marginBottom: 6 }}>
                <b>{it.type}</b> (step {it.step}): {it.details}
                {it.recommendation ? (
                  <div style={{ fontSize: 12, opacity: 0.8 }}>
                    Recommendation: {it.recommendation}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {conflicts.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 600 }}>Conflicts</div>
          <ul style={{ marginTop: 6 }}>
            {conflicts.map((c: any, idx: number) => (
              <li key={idx} style={{ marginBottom: 6 }}>
                <b>{c.topic}</b>
                {c.recommendation ? (
                  <div style={{ fontSize: 12, opacity: 0.8 }}>
                    Recommendation: {c.recommendation}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {missing.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 600 }}>Missing Info</div>
          <ul style={{ marginTop: 6 }}>
            {missing.map((m: string, idx: number) => (
              <li key={idx}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {issues.length === 0 && conflicts.length === 0 && missing.length === 0 && (
        <div style={{ marginTop: 10, fontSize: 13, opacity: 0.8 }}>
          No issues found.
        </div>
      )}
    </div>
  );
}
