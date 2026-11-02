import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { THEME } from "../theme";

export interface CalloutRingProps {
  x: number;
  y: number;
  label: string;
  sublabel?: string;
  variant?: "ok" | "alarm" | "accent";
  durationInFrames?: number;
}

export const CalloutRing: React.FC<CalloutRingProps> = ({
  x,
  y,
  label,
  sublabel,
  variant = "ok",
  durationInFrames = 120,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const inFrames = Math.round(0.3 * fps);
  const outFrames = Math.round(0.3 * fps);

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

  // Continuous pulse effect (1-second cycle)
  const pulsePhase = (frame % 30) / 30;
  const pulseScale = 1 + pulsePhase * 0.8;
  const pulseOpacity = (1 - pulsePhase) * 0.7;

  const color =
    variant === "alarm"
      ? THEME.alarm
      : variant === "accent"
      ? THEME.accent
      : THEME.ok;

  return (
    <AbsoluteFill style={{ pointerEvents: "none", fontFamily: THEME.fontFamily }}>
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          opacity,
          transform: "translate(-50%, -50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 8,
        }}
      >
        {/* Pulsing Ring Center */}
        <div style={{ position: "relative", width: 44, height: 44 }}>
          {/* Expanding pulse */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              border: `2px solid ${color}`,
              transform: `scale(${pulseScale})`,
              opacity: pulseOpacity,
            }}
          />
          {/* Inner core */}
          <div
            style={{
              position: "absolute",
              inset: 6,
              borderRadius: "50%",
              background: "rgba(21, 26, 32, 0.85)",
              border: `2.5px solid ${color}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `0 0 16px ${color}`,
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: color,
              }}
            />
          </div>
        </div>

        {/* Floating Tooltip Label */}
        <div
          style={{
            background: "rgba(15, 19, 23, 0.94)",
            border: `1px solid ${THEME.line2}`,
            borderRadius: 6,
            padding: "6px 12px",
            boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 700, color: "#fff", fontFamily: THEME.fontMono }}>
            {label}
          </span>
          {sublabel && (
            <span style={{ fontSize: 11, color: THEME.muted, fontFamily: THEME.fontMono }}>
              {sublabel}
            </span>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
