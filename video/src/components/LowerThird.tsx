import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export interface LowerThirdProps {
  model: "spark" | "voice" | "sam" | "code";
  modelLabel: string;
  text: string;
  subtext?: string;
  sideNote?: string;
  durationInFrames?: number;
}

export const LowerThird: React.FC<LowerThirdProps> = ({
  model,
  modelLabel,
  text,
  subtext,
  sideNote,
  durationInFrames = 120,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const inFrames = Math.round(0.4 * fps);
  const outFrames = Math.round(0.4 * fps);

  const opacity = interpolate(
    frame,
    [0, inFrames, durationInFrames - outFrames, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }
  );

  const translateX = interpolate(
    frame,
    [0, inFrames, durationInFrames - outFrames, durationInFrames],
    [-24, 0, 0, -16],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }
  );

  const modelColor =
    model === "spark"
      ? THEME.spark
      : model === "voice"
      ? THEME.voice
      : model === "sam"
      ? THEME.sam
      : THEME.code;

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "flex-end",
        paddingBottom: 90, // Keep bottom safe margin above console footer
        paddingLeft: 60,
        pointerEvents: "none",
        fontFamily: THEME.fontFamily,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateX(${translateX}px)`,
          display: "flex",
          alignItems: "stretch",
          background: "rgba(15, 19, 23, 0.94)",
          border: `1px solid ${THEME.line2}`,
          borderLeft: `4px solid ${modelColor}`,
          borderRadius: 8,
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.5)",
          overflow: "hidden",
          maxWidth: 960,
        }}
      >
        <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: THEME.fontMono,
                fontSize: 11,
                fontWeight: 700,
                color: modelColor,
                background: "rgba(255, 255, 255, 0.05)",
                padding: "2px 8px",
                borderRadius: 4,
                letterSpacing: "0.5px",
                textTransform: "uppercase",
              }}
            >
              {modelLabel}
            </span>
            {sideNote && (
              <span style={{ fontSize: 11, color: THEME.dim, fontFamily: THEME.fontMono }}>
                {sideNote}
              </span>
            )}
          </div>
          <div style={{ fontSize: 17, fontWeight: 600, color: "#ffffff", letterSpacing: "0.1px" }}>
            {text}
          </div>
          {subtext && (
            <div style={{ fontSize: 13, color: THEME.muted, fontFamily: THEME.fontMono }}>
              {subtext}
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
