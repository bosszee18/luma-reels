import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, mediaUrl, errMsg } from "@/lib/api";
import { MODES, STATUS } from "@/lib/modes";
import { ModeBadge } from "@/components/ModeCard";
import { ProgressBar } from "@/components/StageTimeline";
import { ScoreRing } from "@/components/ScoreRing";
import { Empty } from "@/pages/Studio";

export default function Projects() {
  const api = useApi();
  const [list, setList] = useState(null);
  const [mode, setMode] = useState("");
  const load = () => api.get("/projects", { params: mode ? { mode } : {} }).then((r) => setList(r.data)).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [api, mode]);
  const del = async (id) => {
    if (!window.confirm("Arsipkan proyek ini?")) return;
    try { await api.delete(`/projects/${id}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-8">
      <div className="rise"><p className="tag">Pustaka</p><h1 className="mt-2 text-4xl sm:text-5xl font-serif tracking-tight">Proyek & aset</h1></div>
      <div className="flex flex-wrap gap-2">
        {[["", "Semua"], ...Object.values(MODES).map((m) => [m.key, m.name])].map(([k, l]) => (
          <button key={k || "all"} type="button" onClick={() => setMode(k)} data-testid={`projects-filter-${k || "all"}`}
            className={`px-3.5 py-1.5 rounded-full border text-sm ${mode === k ? "border-[#F3D9A2]/60 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{l}</button>
        ))}
      </div>
      {list && list.length === 0 && <Empty icon={FolderOpen} text="Belum ada proyek. Mulai dari Studio." />}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(list || []).map((p) => (
          <div key={p.id} className="group relative rounded-2xl border border-[#F3D9A2]/10 bg-[#140F1D]/80 p-4 hover:border-[#F3D9A2]/30 transition-colors" data-testid={`project-card-${p.id}`}>
            <Link to={`/proyek/${p.id}`} className="flex gap-4" data-testid={`project-open-${p.id}`}>
              <div className="h-28 w-16 rounded-lg overflow-hidden bg-[#0B080F] shrink-0 border border-[#F3D9A2]/10">{p.thumb && <img src={mediaUrl(p.thumb)} alt="" className="h-full w-full object-cover" />}</div>
              <div className="flex-1 min-w-0 space-y-2">
                <ModeBadge mode={p.mode} />
                <p className="text-[#FAF7F2] line-clamp-2">{p.title}</p>
                <span className={`inline-block text-[11px] px-2 py-0.5 rounded-full border ${STATUS[p.status]?.cls}`}>{STATUS[p.status]?.label}</span>
                {["queued", "processing"].includes(p.status) ? <ProgressBar value={p.progress} color={MODES[p.mode].color} />
                  : <p className="text-xs text-[#7B6F8E]">{p.video_count} video • {p.approved} final • {new Date(p.created_at).toLocaleDateString("id-ID")}</p>}
              </div>
              {p.best_score ? <ScoreRing score={p.best_score} size={42} /> : null}
            </Link>
            <button type="button" onClick={() => del(p.id)} className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 text-[#7B6F8E] hover:text-red-300 transition-opacity" data-testid={`project-delete-${p.id}`}><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
