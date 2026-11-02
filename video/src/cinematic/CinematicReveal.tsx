import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { BackgroundGrid } from "./BackgroundGrid";
import { Act1TheCrisis } from "./Act1TheCrisis";
import { Act2ProductEntrance } from "./Act2ProductEntrance";
import { Act3TargetLock } from "./Act3TargetLock";
import { Act4Outro } from "./Act4Outro";

export const CinematicReveal: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#070a0e",
        overflow: "hidden",
      }}
    >
      {/* Background Animated Energy Grid (Persists across all acts) */}
      <BackgroundGrid />

      {/* Act 1: The Crisis (0:00 - 0:03, 90 frames) */}
      <Sequence durationInFrames={90} name="The Crisis">
        <Act1TheCrisis />
      </Sequence>

      {/* Act 2: Product Entrance & Meta Models (0:03 - 0:07, 120 frames) */}
      <Sequence from={90} durationInFrames={120} name="Product Entrance">
        <Act2ProductEntrance />
      </Sequence>

      {/* Act 3: Precision Target Lock & Speed Metrics (0:07 - 0:11, 120 frames) */}
      <Sequence from={210} durationInFrames={120} name="Precision & Speed">
        <Act3TargetLock />
      </Sequence>

      {/* Act 4: Outro Lockup & Thesis (0:11 - 0:14, 90 frames) */}
      <Sequence from={330} durationInFrames={90} name="Outro & Thesis">
        <Act4Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
