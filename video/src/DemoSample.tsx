import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { THEME } from "./theme";
import { OpeningTitle } from "./components/OpeningTitle";
import { ReadDecideFlow } from "./components/ReadDecideFlow";
import { LowerThird } from "./components/LowerThird";
import { MetricsOverlay } from "./components/MetricsOverlay";
import { CalloutRing } from "./components/CalloutRing";
import { EndCard } from "./components/EndCard";

export const DemoSample: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: THEME.bg,
        fontFamily: THEME.fontFamily,
        color: THEME.text,
        overflow: "hidden",
      }}
    >
      {/* 1. Opening Title (0:00 - 0:04, 120 frames) */}
      <Sequence durationInFrames={120} name="Opening Title">
        <OpeningTitle />
      </Sequence>

      {/* 2. Read / Decide Architecture Flow (0:04 - 0:08, 120 frames) */}
      <Sequence from={120} durationInFrames={120} name="Read & Decide Pipeline">
        <ReadDecideFlow />
      </Sequence>

      {/* 3. Lower Third Fact Check (0:08 - 0:12, 120 frames) */}
      <Sequence from={240} durationInFrames={120} name="Lower Third Caption">
        <LowerThird
          model="spark"
          modelLabel="Muse Spark + Voice Transcribe"
          text="Voice Transcribe has no Sinhala, so Muse Spark listens to the audio"
          subtext="Fact check: code discards any model line that alters a number or street"
          sideNote="Zero LLM Hallucinations"
          durationInFrames={120}
        />
      </Sequence>

      {/* 4. Switching Metrics & Hospital Generator Priority (0:12 - 0:16, 120 frames) */}
      <Sequence from={360} durationInFrames={120} name="Restoration Metrics">
        <MetricsOverlay />
        <CalloutRing
          x={1350}
          y={360}
          label="Hospital Rd Recloser"
          sublabel="95% Confidence • Safe Switching"
          variant="ok"
          durationInFrames={120}
        />
      </Sequence>

      {/* 5. End Outro Card (0:16 - 0:20, 120 frames) */}
      <Sequence from={480} durationInFrames={120} name="Outro & Attribution">
        <EndCard />
      </Sequence>

      {/* Persistent Footer Disclaimer across all sequences (DEMO.md requirement) */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: 0,
          right: 0,
          textAlign: "center",
          fontSize: 11,
          fontFamily: THEME.fontMono,
          color: THEME.dim,
          letterSpacing: "0.2px",
          pointerEvents: "none",
          zIndex: 100,
        }}
      >
        Demo data: customers are fictional • voices are synthetic • OSM © OpenStreetMap contributors
      </div>
    </AbsoluteFill>
  );
};
