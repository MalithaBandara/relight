import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const inFrames = Math.round(0.4 * fps);

  const opacity = interpolate(frame, [0, inFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const translateY = interpolate(frame, [0, inFrames], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(11, 14, 17, 0.96)",
        fontFamily: THEME.fontFamily,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 20,
          textAlign: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: THEME.accent,
              boxShadow: `0 0 20px ${THEME.accent}`,
            }}
          />
          <span
            style={{
              fontSize: 60,
              fontWeight: 800,
              letterSpacing: "1.5px",
              color: "#ffffff",
              textTransform: "uppercase",
            }}
          >
            Relight
          </span>
        </div>

        <div style={{ fontSize: 22, color: THEME.text, maxWidth: 640 }}>
          Meta models read. Deterministic code locates and decides.
        </div>

        <div
          style={{
            marginTop: 8,
            fontSize: 16,
            fontFamily: THEME.fontMono,
            color: THEME.accent,
            background: "rgba(74, 163, 223, 0.1)",
            border: `1px solid rgba(74, 163, 223, 0.3)`,
            borderRadius: 8,
            padding: "8px 20px",
          }}
        >
          github.com/MalithaBandara/relight
        </div>

        <div
          style={{
            marginTop: 24,
            fontSize: 12,
            fontFamily: THEME.fontMono,
            color: THEME.dim,
          }}
        >
          Customers are fictional • Voices are synthetic • OpenStreetMap © Contributors (ODbL)
        </div>
      </div>
    </AbsoluteFill>
  );
};
