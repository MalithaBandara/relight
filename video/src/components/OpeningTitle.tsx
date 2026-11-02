import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export const OpeningTitle: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 0.4s ease-out in, 0.4s ease-out exit
  const inFrames = Math.round(0.4 * fps);
  const outFrames = Math.round(0.4 * fps);
  const totalFrames = 120; // 4s

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
    [24, 0, 0, -16],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }
  );

  const scale = interpolate(frame, [0, totalFrames], [0.98, 1.02], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
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
          opacity,
          transform: `translateY(${translateY}px) scale(${scale})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
          padding: "36px 56px",
          background: "rgba(21, 26, 32, 0.94)",
          backdropFilter: "blur(12px)",
          border: `1px solid ${THEME.line2}`,
          borderRadius: 12,
          boxShadow: "0 24px 64px rgba(0, 0, 0, 0.6)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: THEME.accent,
              boxShadow: `0 0 16px ${THEME.accent}`,
            }}
          />
          <span
            style={{
              fontSize: 54,
              fontWeight: 800,
              letterSpacing: "1px",
              color: "#ffffff",
              textTransform: "uppercase",
            }}
          >
            Relight
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              fontFamily: THEME.fontMono,
              color: THEME.accent,
              padding: "4px 10px",
              background: "rgba(74, 163, 223, 0.15)",
              border: `1px solid rgba(74, 163, 223, 0.4)`,
              borderRadius: 20,
              marginLeft: 8,
            }}
          >
            PUSH THE FRONTIER
          </span>
        </div>

        <div
          style={{
            fontSize: 24,
            fontWeight: 500,
            color: THEME.text,
            letterSpacing: "0.2px",
          }}
        >
          Meta models read. Deterministic code locates and decides.
        </div>

        <div
          style={{
            fontSize: 14,
            color: THEME.muted,
            fontFamily: THEME.fontMono,
          }}
        >
          AI Outage Agent for Electric Distribution Utilities
        </div>
      </div>
    </AbsoluteFill>
  );
};
