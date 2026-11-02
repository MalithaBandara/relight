import React from "react";
import { useCurrentFrame } from "remotion";

export const AudioVisualizer: React.FC<{ count?: number; color?: string; height?: number }> = ({
  count = 24,
  color = "#a98be8",
  height = 40,
}) => {
  const frame = useCurrentFrame();

  const bars = Array.from({ length: count }, (_, i) => {
    // Generate deterministic fluid waveform height
    const wave =
      Math.sin(frame * 0.15 + i * 0.4) * 0.4 +
      Math.cos(frame * 0.08 + i * 0.25) * 0.3 +
      Math.sin(frame * 0.25 + i * 0.8) * 0.3;
    const barHeight = Math.max(4, Math.abs(wave) * height);

    return (
      <div
        key={i}
        style={{
          width: 3,
          height: barHeight,
          backgroundColor: color,
          borderRadius: 2,
          opacity: 0.85,
          boxShadow: `0 0 6px ${color}66`,
        }}
      />
    );
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 3,
        height: height + 10,
      }}
    >
      {bars}
    </div>
  );
};
