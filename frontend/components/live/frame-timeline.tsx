"use client";

import type { BrowserFrame } from "../../lib/types";

export function FrameTimeline({
  frames,
  selectedEventId,
  onSelect,
}: {
  frames: BrowserFrame[];
  selectedEventId: string | null;
  onSelect: (frame: BrowserFrame) => void;
}) {
  return (
    <section className="sp-card sp-rise sp-d3 p-3">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">帧时间线</h3>
        <span className="font-mono text-xs text-slate-400">
          {frames.length} frames
        </span>
      </div>
      {frames.length === 0 ? (
        <div className="grid h-24 place-items-center text-sm text-slate-400">
          暂无截图 artifact
        </div>
      ) : (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {frames.map((frame, index) => (
            <button
              key={frame.eventId}
              onClick={() => onSelect(frame)}
              className={`w-32 shrink-0 overflow-hidden rounded-xl border text-left transition-all duration-200 ${
                selectedEventId === frame.eventId
                  ? "border-run shadow-glow ring-2 ring-blue-100"
                  : "border-line hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-card"
              }`}
            >
              <div className="h-20 bg-night">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={frame.src}
                  alt={`frame ${index + 1}`}
                  className="h-full w-full object-cover"
                />
              </div>
              <div className="px-2 py-1.5 text-xs">
                <div className="font-mono font-semibold">#{index + 1}</div>
                <div className="truncate text-slate-400">
                  {frame.action ?? frame.artifactPath ?? "browser_frame"}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
