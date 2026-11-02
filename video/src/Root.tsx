import React from "react";
import { Composition } from "remotion";
import { CinematicReveal } from "./cinematic/CinematicReveal";
import { DemoSample } from "./DemoSample";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CinematicReveal"
        component={CinematicReveal}
        durationInFrames={420}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="DemoSample"
        component={DemoSample}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
