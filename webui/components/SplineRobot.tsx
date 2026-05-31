'use client';

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

export function SplineRobot() {
  return (
    <Card className="w-full bg-black/[0.96] relative overflow-hidden border-glow" style={{ height: '450px' }}>
      <Spotlight
        className="-top-40 left-0 md:left-60 md:-top-20"
        size={400}
      />

      {/* 3D 机器人 */}
      <div className="w-full h-full">
        <SplineScene
          scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
          className="w-full h-full"
        />
      </div>
    </Card>
  );
}
