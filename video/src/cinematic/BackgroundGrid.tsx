import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const BackgroundGrid: React.FC = () => {
  const frame = useCurrentFrame();

  // Subtle ambient drift for glow orbs
  const orb1X = 25 + Math.sin(frame * 0.02) * 8;
  const orb1Y = 30 + Math.cos(frame * 0.02) * 6;
  const orb2X = 75 + Math.cos(frame * 0.025) * 8;
  const orb2Y = 65 + Math.sin(frame * 0.025) * 6;

  // Grid scan line translation
  const scanLineY = (frame * 3) % 1080;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#070a0e",
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      {/* Dynamic Ambient Gradient Orbs */}
      <div
        style={{
          position: "absolute",
          left: `${orb1X}%`,
          top: `${orb1Y}%`,
          width: 800,
          height: 800,
          transform: "translate(-50%, -50%)",
          background: "radial-gradient(circle, rgba(74, 163, 223, 0.18) 0%, rgba(74, 163, 223, 0) 70%)",
          filter: "blur(60px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: `${orb2X}%`,
          top: `${orb2Y}%`,
          width: 750,
          height: 750,
          transform: "translate(-50%, -50%)",
          background: "radial-gradient(circle, rgba(169, 139, 232, 0.14) 0%, rgba(169, 139, 232, 0) 70%)",
          filter: "blur(70px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "85%",
          width: 900,
          height: 500,
          transform: "translate(-50%, -50%)",
          background: "radial-gradient(circle, rgba(63, 180, 124, 0.12) 0%, rgba(63, 180, 124, 0) 70%)",
          filter: "blur(80px)",
        }}
      />

      {/* High-Tech Perspective Grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          maskImage: "radial-gradient(ellipse 90% 80% at 50% 50%, #000 30%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 90% 80% at 50% 50%, #000 30%, transparent 80%)",
        }}
      />

      {/* Subtle Laser Scan Line */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: scanLineY,
          height: 1,
          background: "linear-gradient(90deg, transparent, rgba(74, 163, 223, 0.4), transparent)",
          boxShadow: "0 0 12px rgba(74, 163, 223, 0.6)",
        }}
      />

      {/* Top HUD Telemetry Corner Elements */}
      <div
        style={{
          position: "absolute",
          top: 36,
          left: 48,
          fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
          fontSize: 10,
          color: "rgba(133, 146, 161, 0.6)",
          letterSpacing: "1.5px",
          display: "flex",
          gap: 24,
        }}
      >
        <span>FEEDER: 34-BUS / RADIAL</span>
        <span>SYS FREQ: 50.02 HZ</span>
        <span>LAT: 6.0535° N</span>
        <span>LON: 80.2210° E</span>
      </div>

      <div
        style={{
          position: "absolute",
          top: 36,
          right: 48,
          fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
          fontSize: 10,
          color: "rgba(133, 146, 161, 0.6)",
          letterSpacing: "1.5px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            backgroundColor: "#3fb47c",
            boxShadow: "0 0 8px #3fb47c",
          }}
        />
        <span>TELEMETRY: LIVE</span>
      </div>
    </AbsoluteFill>
  );
};
