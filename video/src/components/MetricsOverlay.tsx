import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export const MetricsOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const totalFrames = 120; // 4s
  const inFrames = Math.round(0.4 * fps);
  const outFrames = Math.round(0.4 * fps);

  const opacity = interpolate(
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

  // Animated counter for restored customers: 0 -> 115
  const restoredCount = Math.floor(
    interpolate(frame, [15, 60], [0, 115], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    })
  );

  // Width of comparative timeline bars
  const beforeBarWidth = interpolate(frame, [25, 65], [0, 85], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const afterBarWidth = interpolate(frame, [35, 75], [0, 52], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        paddingBottom: 90,
        pointerEvents: "none",
        fontFamily: THEME.fontFamily,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          width: 980,
          background: "rgba(15, 19, 23, 0.95)",
          border: `1px solid ${THEME.line2}`,
          borderRadius: 12,
          padding: "24px 32px",
          boxShadow: "0 20px 50px rgba(0,0,0,0.6)",
          display: "grid",
          gridTemplateColumns: "240px 1px 1fr",
          gap: 28,
          alignItems: "center",
        }}
      >
        {/* Metric 1: Restored Customers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div
            style={{
              fontSize: 11,
              fontFamily: THEME.fontMono,
              color: THEME.muted,
              textTransform: "uppercase",
              letterSpacing: "0.8px",
            }}
          >
            Safe Switching Result
          </div>
          <div
            style={{
              fontSize: 52,
              fontWeight: 800,
              fontFamily: THEME.fontMono,
              color: THEME.ok,
              lineHeight: 1,
            }}
          >
            {restoredCount}
          </div>
          <div style={{ fontSize: 13, color: THEME.text }}>
            Customers Restored Ahead of Field Repair
          </div>
        </div>

        {/* Vertical Divider */}
        <div style={{ width: 1, height: "100%", background: THEME.line }} />

        {/* Metric 2: Hospital Generator Triage Before / After */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>
              Critical Facility Prioritization: Hospital Generator Failure
            </span>
            <span
              style={{
                fontFamily: THEME.fontMono,
                fontSize: 11,
                color: THEME.alarm,
                background: "rgba(229, 72, 77, 0.15)",
                border: `1px solid rgba(229, 72, 77, 0.3)`,
                borderRadius: 4,
                padding: "2px 8px",
                fontWeight: 600,
              }}
            >
              Priority +1500 (Ahead of Live Wire)
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {/* Standard Queue */}
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  width: 140,
                  fontSize: 12,
                  fontFamily: THEME.fontMono,
                  color: THEME.muted,
                }}
              >
                Standard Triage:
              </span>
              <div
                style={{
                  flex: 1,
                  height: 18,
                  background: THEME.panel,
                  borderRadius: 4,
                  overflow: "hidden",
                  display: "flex",
                }}
              >
                <div
                  style={{
                    width: `${beforeBarWidth}%`,
                    height: "100%",
                    background: THEME.dim,
                    borderRadius: 4,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    paddingRight: 8,
                    fontSize: 11,
                    fontFamily: THEME.fontMono,
                    color: "#fff",
                  }}
                >
                  02:48
                </div>
              </div>
            </div>

            {/* With Relight Priority Bump */}
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  width: 140,
                  fontSize: 12,
                  fontFamily: THEME.fontMono,
                  color: THEME.accent,
                  fontWeight: 600,
                }}
              >
                Relight Priority:
              </span>
              <div
                style={{
                  flex: 1,
                  height: 18,
                  background: THEME.panel,
                  borderRadius: 4,
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <div
                  style={{
                    width: `${afterBarWidth}%`,
                    height: "100%",
                    background: THEME.ok,
                    borderRadius: 4,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    paddingRight: 8,
                    fontSize: 11,
                    fontFamily: THEME.fontMono,
                    color: "#000",
                    fontWeight: 700,
                  }}
                >
                  01:44
                </div>
                <span
                  style={{
                    marginLeft: 12,
                    fontSize: 12,
                    fontFamily: THEME.fontMono,
                    fontWeight: 700,
                    color: THEME.ok,
                  }}
                >
                  ⚡ Restored 64 Minutes Sooner
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
