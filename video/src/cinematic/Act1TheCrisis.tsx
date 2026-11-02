import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AudioVisualizer } from "./AudioVisualizer";

export const Act1TheCrisis: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Snappy spring entrances
  const title1Spring = spring({ frame: frame - 5, fps, config: { damping: 14, stiffness: 140 } });
  const title2Spring = spring({ frame: frame - 18, fps, config: { damping: 14, stiffness: 140 } });
  const badgeSpring = spring({ frame: frame - 2, fps, config: { damping: 12, stiffness: 180 } });
  const card1Spring = spring({ frame: frame - 32, fps, config: { damping: 13, stiffness: 120 } });
  const card2Spring = spring({ frame: frame - 45, fps, config: { damping: 13, stiffness: 120 } });

  // Camera slow cinematic push-in
  const cameraScale = interpolate(frame, [0, 100], [1, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Fade out transition at the end of Act 1
  const fadeOut = interpolate(frame, [80, 95], [1, 0], {
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
        transform: `scale(${cameraScale})`,
        fontFamily: '"IBM Plex Sans", -apple-system, sans-serif',
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 20,
          textAlign: "center",
          zIndex: 10,
        }}
      >
        {/* Urgent Alarm Pill */}
        <div
          style={{
            transform: `scale(${badgeSpring})`,
            opacity: badgeSpring,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 14px",
            background: "rgba(229, 72, 77, 0.15)",
            border: "1px solid rgba(229, 72, 77, 0.4)",
            borderRadius: 24,
            boxShadow: "0 0 24px rgba(229, 72, 77, 0.3)",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: "#e5484d",
              boxShadow: "0 0 10px #e5484d",
            }}
          />
          <span
            style={{
              fontFamily: '"IBM Plex Mono", monospace',
              fontSize: 12,
              fontWeight: 700,
              color: "#ff6b6b",
              letterSpacing: "1px",
              textTransform: "uppercase",
            }}
          >
            Substation Lockout • 1,951 Customers Dark
          </span>
        </div>

        {/* Masked Headline 1 */}
        <div style={{ overflow: "hidden", height: 72 }}>
          <div
            style={{
              transform: `translateY(${(1 - title1Spring) * 80}px)`,
              fontSize: 64,
              fontWeight: 800,
              letterSpacing: "-1.5px",
              color: "#ffffff",
              lineHeight: 1.1,
            }}
          >
            WHEN THE GRID FAILS
          </div>
        </div>

        {/* Masked Headline 2 */}
        <div style={{ overflow: "hidden", height: 44 }}>
          <div
            style={{
              transform: `translateY(${(1 - title2Spring) * 60}px)`,
              fontSize: 32,
              fontWeight: 500,
              color: "#94a3b8",
              letterSpacing: "-0.5px",
            }}
          >
            Phones ring in dozens of languages. Zero ground visibility.
          </div>
        </div>

        {/* Floating Call Ingestion Stream Cards */}
        <div
          style={{
            marginTop: 24,
            display: "flex",
            gap: 16,
            alignItems: "center",
          }}
        >
          {/* Card 1: Sinhala Audio */}
          <div
            style={{
              transform: `translateY(${(1 - card1Spring) * 30}px) scale(${card1Spring})`,
              opacity: card1Spring,
              background: "rgba(21, 26, 32, 0.85)",
              border: "1px solid rgba(169, 139, 232, 0.3)",
              backdropFilter: "blur(16px)",
              borderRadius: 10,
              padding: "12px 18px",
              display: "flex",
              alignItems: "center",
              gap: 14,
              boxShadow: "0 12px 30px rgba(0, 0, 0, 0.4)",
            }}
          >
            <div style={{ textAlign: "left" }}>
              <div
                style={{
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#a98be8",
                }}
              >
                CALLER C02 [SINHALA]
              </div>
              <div style={{ fontSize: 13, color: "#d6dde5", marginTop: 2 }}>
                "Hospital Road ... a pole has fallen"
              </div>
            </div>
            <AudioVisualizer count={16} color="#a98be8" height={26} />
          </div>

          {/* Card 2: Urgent Live Wire Hazard */}
          <div
            style={{
              transform: `translateY(${(1 - card2Spring) * 30}px) scale(${card2Spring})`,
              opacity: card2Spring,
              background: "rgba(21, 26, 32, 0.85)",
              border: "1px solid rgba(229, 72, 77, 0.4)",
              backdropFilter: "blur(16px)",
              borderRadius: 10,
              padding: "12px 18px",
              display: "flex",
              alignItems: "center",
              gap: 14,
              boxShadow: "0 12px 30px rgba(0, 0, 0, 0.4)",
            }}
          >
            <div style={{ textAlign: "left" }}>
              <div
                style={{
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#ff6b6b",
                }}
              >
                HAZARD H2 [SPARKING WIRE]
              </div>
              <div style={{ fontSize: 13, color: "#d6dde5", marginTop: 2 }}>
                Escalated Above All Outages
              </div>
            </div>
            <span
              style={{
                fontSize: 11,
                fontFamily: '"IBM Plex Mono", monospace',
                fontWeight: 700,
                color: "#ff6b6b",
                background: "rgba(229, 72, 77, 0.2)",
                padding: "4px 8px",
                borderRadius: 4,
              }}
            >
              RANK #1
            </span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
