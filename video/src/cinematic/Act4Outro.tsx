import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const Act4Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Snappy spring animations
  const logoSpring = spring({ frame: frame - 4, fps, config: { damping: 14, stiffness: 130 } });
  const textSpring = spring({ frame: frame - 16, fps, config: { damping: 14, stiffness: 130 } });
  const badgeSpring = spring({ frame: frame - 28, fps, config: { damping: 12, stiffness: 160 } });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: '"IBM Plex Sans", -apple-system, sans-serif',
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 22,
          textAlign: "center",
          zIndex: 10,
        }}
      >
        {/* Glow Badge */}
        <div
          style={{
            transform: `scale(${badgeSpring})`,
            opacity: badgeSpring,
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "6px 16px",
            background: "rgba(74, 163, 223, 0.15)",
            border: "1px solid rgba(74, 163, 223, 0.4)",
            borderRadius: 24,
            boxShadow: "0 0 24px rgba(74, 163, 223, 0.25)",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: "#4aa3df",
              boxShadow: "0 0 10px #4aa3df",
            }}
          />
          <span
            style={{
              fontFamily: '"IBM Plex Mono", monospace',
              fontSize: 12,
              fontWeight: 700,
              color: "#4aa3df",
              letterSpacing: "1px",
              textTransform: "uppercase",
            }}
          >
            Meta Global AI Hackathon 2026 • Push the Frontier
          </span>
        </div>

        {/* Hero Logo */}
        <div style={{ overflow: "hidden", height: 96 }}>
          <div
            style={{
              transform: `translateY(${(1 - logoSpring) * 96}px)`,
              fontSize: 88,
              fontWeight: 900,
              letterSpacing: "-2px",
              background: "linear-gradient(135deg, #ffffff 40%, #4aa3df 80%, #3fb47c 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              lineHeight: 1,
              textTransform: "uppercase",
            }}
          >
            RELIGHT
          </div>
        </div>

        {/* Core Thesis Statement */}
        <div style={{ overflow: "hidden", height: 44 }}>
          <div
            style={{
              transform: `translateY(${(1 - textSpring) * 44}px)`,
              fontSize: 26,
              fontWeight: 600,
              color: "#d6dde5",
              letterSpacing: "-0.2px",
            }}
          >
            Meta models read. Deterministic code decides.
          </div>
        </div>

        {/* Repo Pill */}
        <div
          style={{
            transform: `scale(${badgeSpring})`,
            opacity: badgeSpring,
            marginTop: 10,
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 16,
            fontWeight: 600,
            color: "#ffffff",
            background: "rgba(255, 255, 255, 0.06)",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: 8,
            padding: "10px 24px",
            boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
          }}
        >
          github.com/MalithaBandara/relight
        </div>

        {/* Disclaimer Footer */}
        <div
          style={{
            marginTop: 32,
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 11,
            color: "#5f6b78",
            letterSpacing: "0.5px",
          }}
        >
          Demo data: customers are fictional • voices are synthetic • OSM © OpenStreetMap contributors (ODbL)
        </div>
      </div>
    </AbsoluteFill>
  );
};
