import { Check, Loader2, AlertTriangle, Circle } from "lucide-react";

const Icon = ({ status, color }) => {
  if (status === "done") return <Check className="h-3.5 w-3.5" style={{ color }} />;
  if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-[#F3D9A2]" />;
  if (status === "failed") return <AlertTriangle className="h-3.5 w-3.5 text-red-300" />;
  return <Circle className="h-3 w-3 text-[#7B6F8E]" />;
};

export const ProgressBar = ({ value, color = "#F3D9A2", testid }) => (
  <div className="h-1.5 rounded-full bg-[#F3D9A2]/10 overflow-hidden" data-testid={testid}>
    <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.round((value || 0) * 100)}%`, background: color }} />
  </div>
);

export const StageTimeline = ({ stages = [], color, compact = false }) => (
  <ol className={compact ? "flex gap-1" : "space-y-3"} data-testid="stage-timeline">
    {stages.map((s) => compact ? (
      <li key={s.key} title={s.label} className="flex-1 h-1.5 rounded-full overflow-hidden bg-[#F3D9A2]/10">
        <div className="h-full" style={{ width: s.status === "done" ? "100%" : s.status === "running" ? `${Math.max(8, s.progress * 100)}%` : 0, background: s.status === "failed" ? "#f87171" : color }} />
      </li>
    ) : (
      <li key={s.key} className="flex gap-3" data-testid={`stage-${s.key}`}>
        <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full grid place-items-center border border-[#F3D9A2]/15 bg-[#140F1D]"><Icon status={s.status} color={color} /></span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className={`text-sm ${s.status === "pending" ? "text-[#7B6F8E]" : "text-[#FAF7F2]"}`}>{s.label}</p>
            <span className="text-xs text-[#7B6F8E]" data-testid={`stage-${s.key}-status`}>
              {s.status === "running" ? `${Math.round(s.progress * 100)}%` : { done: "selesai", failed: "gagal", pending: "menunggu" }[s.status]}
            </span>
          </div>
          {s.status === "running" && <div className="mt-1.5"><ProgressBar value={s.progress} color={color} /></div>}
          {s.message && <p className={`text-xs mt-1 ${s.status === "failed" ? "text-red-300" : "text-[#B5A9C4]"}`}>{s.message}</p>}
        </div>
      </li>
    ))}
  </ol>
);
