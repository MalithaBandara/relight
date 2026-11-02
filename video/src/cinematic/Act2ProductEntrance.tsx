import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const Act2ProductEntrance: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Snappy entrance springs
  const heroSpring = spring({ frame: frame - 2, fps, config: { damping: 14, stiffness: 120 } });
  const subSpring = spring({ frame: frame - 15, fps, config: { damping: 14, stiffness: 120 } });
  const cardSpring = spring({ frame: frame - 25, fps, config: { damping: 13, stiffness: 100 } });

  // 3D Tilt perspective animation: starts tilted, springs flat
  const rotateX = interpolate(cardSpring, [0, 1], [14, 0]);
  const rotateY = interpolate(cardSpring, [0, 1], [-10, 0]);
  const cardScale = interpolate(cardSpring, [0, 1], [0.92, 1]);

  // Specular sheen sweep effect across the card (at frame 40-75)
  const sheenX = interpolate(frame, [35, 75], [-120, 220], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Outro transition
  const fadeOut = interpolate(frame, [105, 120], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeOut,
        fontFamily: '"IBM Plex Sans", -apple-system, sans-serif',
        perspective: 1200,
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
        {/* Brand Tagline Header */}
        <div style={{ overflow: "hidden", height: 76 }}>
          <div
            style={{
              transform: `translateY(${(1 - heroSpring) * 80}px)`,
              fontSize: 72,
              fontWeight: 900,
              letterSpacing: "-2px",
              background: "linear-gradient(135deg, #ffffff 45%, #4aa3df 85%, #a98be8 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              lineHeight: 1.05,
              textTransform: "uppercase",
            }}
          >
            RELIGHT
          </div>
        </div>

        {/* Subtitle */}
        <div style={{ overflow: "hidden", height: 38 }}>
          <div
            style={{
              transform: `translateY(${(1 - subSpring) * 45}px)`,
              fontSize: 22,
              fontWeight: 600,
              color: "#d6dde5",
              letterSpacing: "0.2px",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span>Meta Models Read.</span>
            <span style={{ color: "#4aa3df" }}>•</span>
            <span>Deterministic Code Locates & Decides.</span>
          </div>
        </div>

        {/* 3D Glass Dashboard Card */}
        <div
          style={{
            transform: `scale(${cardScale}) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`,
            opacity: cardSpring,
            width: 880,
            background: "rgba(18, 23, 29, 0.9)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: 16,
            padding: "26px 32px",
            boxShadow: "0 30px 80px rgba(0, 0, 0, 0.7), 0 0 40px rgba(74, 163, 223, 0.15)",
            backdropFilter: "blur(24px)",
            position: "relative",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            gap: 18,
          }}
        >
          {/* Specular Sheen Sweep */}
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: `${sheenX}%`,
              width: 120,
              background:
                "linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.12), transparent)",
              transform: "skewX(-25deg)",
              pointerEvents: "none",
            }}
          />

          {/* Card Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#4aa3df",
                  background: "rgba(74, 163, 223, 0.15)",
                  border: "1px solid rgba(74, 163, 223, 0.3)",
                  borderRadius: 4,
                  padding: "3px 8px",
                }}
              >
                LIVE TRIAGE ENGINE
              </span>
              <span style={{ fontSize: 13, color: "#8592a1", fontFamily: '"IBM Plex Mono", monospace' }}>
                Single source of truth • Zero hallucination
              </span>
            </div>
            <span style={{ fontSize: 12, color: "#3fb47c", fontFamily: '"IBM Plex Mono", monospace' }}>
              ● 3 META MODELS ACTIVE
            </span>
          </div>

          {/* Model Showcase Columns */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 14,
            }}
          >
            {/* Spark */}
            <div
              style={{
                background: "rgba(93, 156, 236, 0.08)",
                border: "1px solid rgba(93, 156, 236, 0.3)",
                borderRadius: 10,
                padding: "16px",
                textAlign: "left",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#5d9cec" }}>
                ✦ Muse Spark 1.3
              </div>
              <div style={{ fontSize: 12, color: "#d6dde5", lineHeight: 1.4 }}>
                JSON schema extraction & Sinhala speech comprehension
              </div>
              <div
                style={{
                  marginTop: 6,
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 10,
                  color: "#8592a1",
                }}
              >
                97% Street Accuracy
              </div>
            </div>

            {/* Voice Transcribe */}
            <div
              style={{
                background: "rgba(169, 139, 232, 0.08)",
                border: "1px solid rgba(169, 139, 232, 0.3)",
                borderRadius: 10,
                padding: "16px",
                textAlign: "left",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#a98be8" }}>
                ✦ Voice Transcribe
              </div>
              <div style={{ fontSize: 12, color: "#d6dde5", lineHeight: 1.4 }}>
                Real-time 24 kHz WebSocket ASR with street keyword biasing
              </div>
              <div
                style={{
                  marginTop: 6,
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 10,
                  color: "#8592a1",
                }}
              >
                11 / 13 Street Names Heard
              </div>
            </div>

            {/* SAM 3.1 */}
            <div
              style={{
                background: "rgba(60, 194, 160, 0.08)",
                border: "1px solid rgba(60, 194, 160, 0.3)",
                borderRadius: 10,
                padding: "16px",
                textAlign: "left",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#3cc2a0" }}>
                ✦ SAM 3.1
              </div>
              <div style={{ fontSize: 12, color: "#d6dde5", lineHeight: 1.4 }}>
                Pole plate identification, wire sag & drone tree tracking
              </div>
              <div
                style={{
                  marginTop: 6,
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 10,
                  color: "#8592a1",
                }}
              >
                Lossless Base85 Masks
              </div>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
