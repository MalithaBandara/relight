import React from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const Act3TargetLock: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Snappy spring animations
  const targetSpring = spring({ frame: frame - 5, fps, config: { damping: 12, stiffness: 160 } });
  const metricsSpring = spring({ frame: frame - 25, fps, config: { damping: 14, stiffness: 130 } });
  const badgeSpring = spring({ frame: frame - 45, fps, config: { damping: 11, stiffness: 180 } });

  // Numerical counter 0 -> 115
  const restoredCount = Math.floor(
    interpolate(frame, [25, 65], [0, 115], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    })
  );

  // Confidence counter 0% -> 95%
  const confCount = Math.floor(
    interpolate(frame, [10, 45], [0, 95], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    })
  );

  // Crosshair brackets expansion
  const bracketOffset = interpolate(targetSpring, [0, 1], [30, 0]);

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
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
          textAlign: "center",
          zIndex: 10,
        }}
      >
        {/* High-Tech HUD Target Lock Frame */}
        <div
          style={{
            position: "relative",
            padding: "24px 48px",
            background: "rgba(15, 20, 26, 0.92)",
            border: "1px solid rgba(63, 180, 124, 0.3)",
            borderRadius: 12,
            boxShadow: "0 20px 60px rgba(0, 0, 0, 0.7), 0 0 30px rgba(63, 180, 124, 0.15)",
            backdropFilter: "blur(20px)",
            opacity: targetSpring,
            transform: `scale(${0.92 + targetSpring * 0.08})`,
            display: "flex",
            alignItems: "center",
            gap: 36,
          }}
        >
          {/* Target Reticle Graphic */}
          <div style={{ position: "relative", width: 90, height: 90 }}>
            {/* Corner Bracket TL */}
            <div
              style={{
                position: "absolute",
                top: -bracketOffset,
                left: -bracketOffset,
                width: 20,
                height: 20,
                borderTop: "3px solid #3fb47c",
                borderLeft: "3px solid #3fb47c",
              }}
            />
            {/* Corner Bracket TR */}
            <div
              style={{
                position: "absolute",
                top: -bracketOffset,
                right: -bracketOffset,
                width: 20,
                height: 20,
                borderTop: "3px solid #3fb47c",
                borderRight: "3px solid #3fb47c",
              }}
            />
            {/* Corner Bracket BL */}
            <div
              style={{
                position: "absolute",
                bottom: -bracketOffset,
                left: -bracketOffset,
                width: 20,
                height: 20,
                borderBottom: "3px solid #3fb47c",
                borderLeft: "3px solid #3fb47c",
              }}
            />
            {/* Corner Bracket BR */}
            <div
              style={{
                position: "absolute",
                bottom: -bracketOffset,
                right: -bracketOffset,
                width: 20,
                height: 20,
                borderBottom: "3px solid #3fb47c",
                borderRight: "3px solid #3fb47c",
              }}
            />

            {/* Inner Radar Circle */}
            <div
              style={{
                position: "absolute",
                inset: 8,
                borderRadius: "50%",
                border: "1px dashed rgba(63, 180, 124, 0.5)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  backgroundColor: "#3fb47c",
                  boxShadow: "0 0 16px #3fb47c",
                }}
              />
            </div>
          </div>

          {/* Target Metadata */}
          <div style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 4 }}>
            <span
              style={{
                fontFamily: '"IBM Plex Mono", monospace',
                fontSize: 11,
                color: "#3fb47c",
                fontWeight: 700,
                letterSpacing: "1px",
              }}
            >
              ✦ FAULT LOCATED VIA DETERMINISTIC TRACER
            </span>
            <span style={{ fontSize: 32, fontWeight: 800, color: "#ffffff" }}>
              Hospital Road Recloser [I1]
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 4 }}>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  fontFamily: '"IBM Plex Mono", monospace',
                  color: "#3fb47c",
                }}
              >
                {confCount}% Confidence
              </span>
              <span style={{ fontSize: 13, color: "#8592a1" }}>
                14 Calls Correlated • Neighbor Silence Accounted
              </span>
            </div>
          </div>
        </div>

        {/* Breakthrough Dual Metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
            width: 820,
            opacity: metricsSpring,
            transform: `translateY(${(1 - metricsSpring) * 30}px)`,
          }}
        >
          {/* Card 1: Safe Switching */}
          <div
            style={{
              background: "rgba(21, 26, 32, 0.85)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: 12,
              padding: "20px 24px",
              textAlign: "left",
              backdropFilter: "blur(16px)",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontFamily: '"IBM Plex Mono", monospace',
                color: "#8592a1",
                textTransform: "uppercase",
              }}
            >
              Operator-Approved Tie Switching
            </div>
            <div
              style={{
                fontSize: 54,
                fontWeight: 800,
                fontFamily: '"IBM Plex Mono", monospace',
                color: "#3fb47c",
                lineHeight: 1,
              }}
            >
              {restoredCount}
            </div>
            <div style={{ fontSize: 13, color: "#d6dde5" }}>
              Customers Restored Before Field Crews Finish
            </div>
          </div>

          {/* Card 2: Hospital Priority Bump */}
          <div
            style={{
              transform: `scale(${badgeSpring})`,
              background: "rgba(21, 26, 32, 0.85)",
              border: "1px solid rgba(229, 72, 77, 0.3)",
              borderRadius: 12,
              padding: "20px 24px",
              textAlign: "left",
              backdropFilter: "blur(16px)",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              position: "relative",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontFamily: '"IBM Plex Mono", monospace',
                color: "#ff6b6b",
                textTransform: "uppercase",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>Emergency Queue Jump</span>
              <span>Priority 1500</span>
            </div>
            <div
              style={{
                fontSize: 48,
                fontWeight: 800,
                fontFamily: '"IBM Plex Mono", monospace',
                color: "#4aa3df",
                lineHeight: 1,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>-64</span>
              <span style={{ fontSize: 24, fontWeight: 600 }}>MINUTES</span>
            </div>
            <div style={{ fontSize: 13, color: "#d6dde5" }}>
              Hospital generator failure detected in call & fast-tracked
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
