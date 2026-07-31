"use client";

import { ExperienceCanvas } from "@/components/ExperienceCanvas";
import { ExperienceHUD, ScrollSpacer } from "@/components/ExperienceHUD";
import { ScrollProvider } from "@/scroll/ScrollProvider";
import dynamic from "next/dynamic";

const Canvas = dynamic(
  () => Promise.resolve({ default: ExperienceCanvas }),
  { ssr: false, loading: () => <div className="fixed inset-0 bg-[#020203]" /> },
);

export function ExperienceRoot() {
  return (
    <ScrollProvider>
      <main className="relative min-h-screen bg-[#020203] text-white">
        <Canvas />
        <ScrollSpacer />
        <ExperienceHUD />
      </main>
    </ScrollProvider>
  );
}
