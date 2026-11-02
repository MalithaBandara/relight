import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export const ReadDecideFlow: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const totalFrames = 120; // 4s
  const inFrames = Math.round(0.4 * fps);
  const outFrames = Math.round(0.4 * fps);

  const containerOpacity = interpolate(
    frame,
    [0, inFrames, totalFrames - outFrames, totalFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }
  );

  const translateY = interpolate(
    frame,
    [0, inFrames, totalFrames - outFrames, totalFrames],
    [20, 0, 0, -10],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // Staggered reveal of nodes
  const leftNodeProgress = interpolate(frame, [10, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const centerNodeProgress = interpolate(frame, [35, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const rightNodeProgress = interpolate(frame, [60, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none",
        fontFamily: THEME.fontFamily,
      }}
    >
      <div
        style={{
          opacity: containerOpacity,
          transform: `translateY(${translateY}px)`,
          width: 1040,
          background: "rgba(15, 19, 23, 0.95)",
          border: `1px solid ${THEME.line2}`,
          borderRadius: 14,
          padding: "28px 36px",
          boxShadow: "0 24px 60px rgba(0,0,0,0.7)",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: THEME.fontMono,
                fontSize: 12,
                color: THEME.accent,
                background: "rgba(74, 163, 223, 0.15)",
                border: `1px solid rgba(74, 163, 223, 0.3)`,
                borderRadius: 4,
                padding: "2px 8px",
                textTransform: "uppercase",
              }}
            >
              Architecture & Decision Pipeline
            </span>
            <span style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>
              How Relight Processes Unstructured Chaos
            </span>
          </div>
          <span style={{ fontSize: 13, fontFamily: THEME.fontMono, color: THEME.muted }}>
            Zero LLM Hallucinations on the Physical Grid
          </span>
        </div>

        {/* 3-Column Diagram */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 40px 1.1fr 40px 1fr",
            alignItems: "center",
            gap: 8,
          }}
        >
          {/* Column 1: Models Reading Inbound Signals */}
          <div
            style={{
              opacity: leftNodeProgress,
              transform: `translateX(${(1 - leftNodeProgress) * -15}px)`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
              background: THEME.panel,
              border: `1px solid ${THEME.line}`,
              borderRadius: 8,
              padding: 16,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: THEME.muted, textTransform: "uppercase" }}>
              1. Meta Models Read
            </div>
            <div
              style={{
                padding: "8px 10px",
                background: "rgba(93, 156, 236, 0.1)",
                border: `1px solid rgba(93, 156, 236, 0.3)`,
                borderRadius: 6,
                fontSize: 12,
                color: THEME.spark,
                fontWeight: 600,
              }}
            >
              ✦ Muse Spark
              <span style={{ display: "block", fontSize: 11, color: THEME.text, fontWeight: 400 }}>
                Multilingual complaints & SMS codes
              </span>
            </div>
            <div
              style={{
                padding: "8px 10px",
                background: "rgba(169, 139, 232, 0.1)",
                border: `1px solid rgba(169, 139, 232, 0.3)`,
                borderRadius: 6,
                fontSize: 12,
                color: THEME.voice,
                fontWeight: 600,
              }}
            >
              ✦ Voice Transcribe
              <span style={{ display: "block", fontSize: 11, color: THEME.text, fontWeight: 400 }}>
                Real-time 24kHz caller audio stream
              </span>
            </div>
            <div
              style={{
                padding: "8px 10px",
                background: "rgba(60, 194, 160, 0.1)",
                border: `1px solid rgba(60, 194, 160, 0.3)`,
                borderRadius: 6,
                fontSize: 12,
                color: THEME.sam,
                fontWeight: 600,
              }}
            >
              ✦ SAM 3.1
              <span style={{ display: "block", fontSize: 11, color: THEME.text, fontWeight: 400 }}>
                Pole plate OCR & drone mask tracking
              </span>
            </div>
          </div>

          {/* Arrow 1 */}
          <div style={{ textAlign: "center", color: THEME.muted, fontSize: 20 }}>➔</div>

          {/* Column 2: Deterministic Tracer (Code) */}
          <div
            style={{
              opacity: centerNodeProgress,
              transform: `scale(${0.95 + centerNodeProgress * 0.05})`,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              background: THEME.panel2,
              border: `1px solid ${THEME.code}`,
              borderRadius: 8,
              padding: 18,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: THEME.text, textTransform: "uppercase" }}>
                2. Deterministic Code Decides
              </div>
              <span
                style={{
                  fontFamily: THEME.fontMono,
                  fontSize: 10,
                  color: "#fff",
                  background: THEME.line2,
                  padding: "2px 6px",
                  borderRadius: 4,
                }}
              >
                Tracer.py
              </span>
            </div>
            <div style={{ fontSize: 13, color: THEME.text, lineHeight: 1.4 }}>
              • Bayesian Log-Likelihood Search
              <br />
              • SCADA Lockout Correlation
              <br />
              • Customer Silence Accounting
              <br />
              • Topological Radial Graph Walk
            </div>
            <div
              style={{
                fontSize: 11,
                fontFamily: THEME.fontMono,
                color: THEME.dim,
                background: THEME.bg,
                padding: 6,
                borderRadius: 4,
              }}
            >
              Code checks candidate safety before any switching suggestion
            </div>
          </div>

          {/* Arrow 2 */}
          <div style={{ textAlign: "center", color: THEME.muted, fontSize: 20 }}>➔</div>

          {/* Column 3: The Located Device Output */}
          <div
            style={{
              opacity: rightNodeProgress,
              transform: `translateX(${(1 - rightNodeProgress) * 15}px)`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
              background: THEME.panel,
              border: `1px solid ${THEME.ok}`,
              borderRadius: 8,
              padding: 16,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: THEME.ok, textTransform: "uppercase" }}>
              3. Operational Action
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#fff" }}>
              Hospital Rd Recloser
            </div>
            <div
              style={{
                fontFamily: THEME.fontMono,
                fontSize: 22,
                fontWeight: 700,
                color: THEME.ok,
              }}
            >
              95% Confidence
            </div>
            <div style={{ fontSize: 12, color: THEME.muted }}>
              Dispatched Line Crew • Isolate-then-restore switching prepared for Operator approval
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
