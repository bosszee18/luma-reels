import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Wand2, Clock } from "lucide-react";
import { useApi, errMsg, fmtTime } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { ScoreRing } from "@/components/ScoreRing";

export const ScorePanel = ({ video, version, onSeek }) => {
  const sc = version?.score ?? video.score;
  const reason = version?.score_reason ?? video.score_reason;
  const sugg = version?.suggestions ?? video.suggestions ?? [];
  return (
    <div className="space-y-4" data-testid="score-panel">
      <div className="flex items-center gap-4">
        <ScoreRing score={sc} size={76} testid="review-editorial-score-badge" />
        <div><p className="tag">Skor editorial</p><p className="text-sm text-[#B5A9C4] mt-1" data-testid="score-reason">{reason || "—"}</p></div>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-semibold">Saran perbaikan</p>
        {sugg.length === 0 && <p className="text-sm text-[#7B6F8E]">Tidak ada saran.</p>}
        {sugg.map((s, i) => (
          <button key={i} type="button" onClick={() => onSeek(Number(s.t) || 0)} data-testid={`suggestion-${i}`}
            className="w-full text-left flex gap-3 rounded-lg border border-[#F3D9A2]/10 p-3 hover:border-[#F3D9A2]/35 transition-colors">
            <span className="text-xs font-mono text-[#F3D9A2] flex items-center gap-1 shrink-0"><Clock className="h-3 w-3" />{fmtTime(s.t)}</span>
            <span className="text-sm text-[#B5A9C4]">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

const TARGETS = {
  clip: [["hook", "Hook pembuka"], ["batas", "Titik mulai/akhir"], ["broll", "B-roll"], ["cta", "CTA penutup"], ["musik", "Musik"]],
  motion: [["hook", "Hook pembuka"], ["tipografi", "Tipografi kinetik"], ["broll", "B-roll & ilustrasi"], ["cta", "CTA"], ["musik", "Musik"]],
  explainer: [["adegan", "Adegan tertentu"], ["hook", "Hook"], ["cta", "CTA"], ["suara", "Suara narasi"], ["musik", "Musik"]],
};

export const RevisePanel = ({ video, getTime, onQueued }) => {
  const api = useApi();
  const kind = video.plan.kind;
  const [target, setTarget] = useState(TARGETS[kind][0][0]);
  const [scene, setScene] = useState(1);
  const [range, setRange] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const revising = video.status === "revising";

  const submit = async () => {
    setBusy(true);
    try {
      const t = target === "adegan" ? `adegan ${scene}` : target;
      await api.post(`/videos/${video.id}/revise`, { instruction: text, target: t, start: range?.[0] ?? null, end: range?.[1] ?? null });
      toast.success("Revisi masuk antrean. Versi baru akan muncul otomatis.");
      setText("");
      onQueued();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  const mark = () => {
    const t = getTime();
    setRange([Math.max(0, +(t - 2).toFixed(1)), +(t + 3).toFixed(1)]);
  };

  return (
    <div className="space-y-4" data-testid="revise-panel">
      {revising && <div className="rounded-lg border border-[#C084FC]/40 bg-[#A855F7]/10 p-3 text-sm text-[#E9D5FF] flex items-center gap-2" data-testid="revising-indicator"><Loader2 className="h-4 w-4 animate-spin" /> Revisi “{video.pending_revision?.instruction}” sedang diproses…</div>}
      {video.revision_error && <p className="text-sm text-red-300">Revisi terakhir gagal: {video.revision_error}</p>}
      <div className="flex flex-wrap gap-2">
        {TARGETS[kind].map(([k, l]) => (
          <button key={k} type="button" onClick={() => setTarget(k)} data-testid={`revise-target-${k}`}
            className={`px-3 py-1.5 rounded-full border text-xs ${target === k ? "border-[#F3D9A2]/60 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{l}</button>
        ))}
      </div>
      {target === "adegan" && (
        <div className="flex flex-wrap gap-2">
          {video.plan.scenes.map((_, i) => (
            <button key={i} type="button" onClick={() => setScene(i + 1)} data-testid={`revise-scene-${i + 1}`}
              className={`h-8 w-8 rounded-full border text-xs ${scene === i + 1 ? "border-[#10B981] text-[#34D399]" : "border-[#F3D9A2]/15 text-[#B5A9C4]"}`}>{i + 1}</button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 text-xs text-[#B5A9C4]">
        <button type="button" onClick={mark} className="px-3 py-1.5 rounded-full border border-[#F3D9A2]/20 hover:border-[#F3D9A2]/50" data-testid="revise-mark-time-button">Tandai posisi pemutar</button>
        {range && <span data-testid="revise-range">{fmtTime(range[0])}–{fmtTime(range[1])}</span>}
      </div>
      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} data-testid="revise-instruction-input" className="bg-[#0B080F]/60"
        placeholder="mis. Buat hook lebih provokatif dan ganti B-roll dengan suasana pasar pagi" />
      <button type="button" disabled={busy || revising || text.trim().length < 3} onClick={submit} data-testid="review-revise-segment-button"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-[#F3D9A2]/40 text-[#F3D9A2] hover:bg-[#F3D9A2]/10 disabled:opacity-40 transition-colors">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />} Revisi bagian ini
      </button>
    </div>
  );
};
