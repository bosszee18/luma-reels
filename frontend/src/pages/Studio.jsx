import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Film, Clock, ArrowRight } from "lucide-react";
import { useApi, mediaUrl } from "@/lib/api";
import { MODES, STATUS } from "@/lib/modes";
import { Prism } from "@/components/Prism";
import { ModeCard, ModeBadge } from "@/components/ModeCard";
import { StageTimeline, ProgressBar } from "@/components/StageTimeline";
import { ScoreRing } from "@/components/ScoreRing";

const JobRow = ({ p }) => {
  const m = MODES[p.mode];
  const cur = p.stages.find((s) => s.status === "running") || p.stages.find((s) => s.status === "failed");
  return (
    <Link to={`/proyek/${p.id}`} className="block rounded-xl border border-[#F3D9A2]/10 bg-[#1A1426]/70 p-4 hover:border-[#F3D9A2]/30 transition-colors" data-testid={`active-job-${p.id}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <ModeBadge mode={p.mode} />
          <p className="mt-2 text-[#FAF7F2] truncate">{p.title}</p>
        </div>
        <span className="font-serif text-3xl text-[#F3D9A2]" data-testid="active-job-percent">{Math.round(p.progress * 100)}%</span>
      </div>
      <div className="mt-3"><StageTimeline stages={p.stages} color={m.color} compact /></div>
      <p className="mt-2 text-xs text-[#B5A9C4]">{p.status === "queued" ? "Menunggu giliran worker…" : cur ? `${cur.label}${cur.message ? " — " + cur.message : ""}` : "Menyiapkan…"}</p>
    </Link>
  );
};

export const ReviewItem = ({ v }) => {
  const last = v.versions[v.versions.length - 1];
  return (
    <Link to={`/proyek/${v.project_id}?video=${v.id}`} className="flex gap-3 items-center rounded-xl border border-[#F3D9A2]/10 bg-[#1A1426]/70 p-3 hover:border-[#F3D9A2]/30 transition-colors" data-testid={`review-queue-item-${v.id}`}>
      <div className="h-20 w-12 rounded-md overflow-hidden bg-[#0B080F] shrink-0">
        {last?.thumb && <img src={mediaUrl(last.thumb)} alt="" className="h-full w-full object-cover" />}
      </div>
      <div className="flex-1 min-w-0">
        <ModeBadge mode={v.mode} />
        <p className="mt-1.5 text-sm text-[#FAF7F2] line-clamp-2">{v.title}</p>
        <p className="text-xs text-[#7B6F8E] mt-0.5">v{last?.n} • {Math.round(last?.duration || 0)} dtk {v.status === "revising" && "• sedang direvisi"}</p>
      </div>
      <ScoreRing score={v.score} size={46} />
    </Link>
  );
};

export default function Studio() {
  const api = useApi();
  const [projects, setProjects] = useState([]);
  const [queue, setQueue] = useState([]);
  const load = useCallback(async () => {
    const [p, q] = await Promise.all([api.get("/projects"), api.get("/review-queue")]);
    setProjects(p.data);
    setQueue(q.data);
  }, [api]);
  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 4000);
    return () => clearInterval(t);
  }, [load]);
  const active = projects.filter((p) => ["queued", "processing"].includes(p.status));
  const recent = projects.filter((p) => p.thumb).slice(0, 8);

  return (
    <div className="space-y-14">
      <section className="grid lg:grid-cols-12 gap-8 items-center">
        <div className="lg:col-span-7 rise">
          <p className="tag">Studio sinematik AI • Bahasa Indonesia</p>
          <h1 className="mt-4 text-4xl sm:text-5xl lg:text-6xl font-serif tracking-tight text-[#FAF7F2] leading-[1.02]">
            Dari bahan mentah<br />ke <em className="text-[#F3D9A2]">Reels siap tayang</em>.
          </h1>
          <p className="mt-5 max-w-xl text-base text-[#B5A9C4] leading-relaxed">
            Unggah, pilih mode, dan biarkan atelier bekerja — transkrip, potongan, subtitle, visual, suara, hingga skor editorial. Anda tinggal mereview dan menyetujui.
          </p>
          <div className="mt-7 flex flex-wrap gap-3 text-xs text-[#B5A9C4]">
            <span className="px-3 py-1.5 rounded-full border border-[#F3D9A2]/15" data-testid="stat-active">{active.length} pekerjaan aktif</span>
            <span className="px-3 py-1.5 rounded-full border border-[#F3D9A2]/15" data-testid="stat-review">{queue.length} menunggu review</span>
            <span className="px-3 py-1.5 rounded-full border border-[#F3D9A2]/15">{projects.length} proyek</span>
          </div>
        </div>
        <div className="lg:col-span-5 hidden sm:flex justify-center"><Prism /></div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {["autoclip", "automotion", "explainer"].map((m, i) => <ModeCard key={m} mode={m} index={i} />)}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-end justify-between">
            <div><p className="tag">Progres tahap nyata</p><h2 className="font-serif text-3xl mt-1">Sedang diproduksi</h2></div>
            <Link to="/proyek" className="text-sm text-[#B5A9C4] hover:text-[#F3D9A2] flex items-center gap-1" data-testid="see-all-projects-link">Semua proyek <ArrowRight className="h-4 w-4" /></Link>
          </div>
          {active.length === 0 && <Empty icon={Clock} text="Belum ada pekerjaan aktif. Pilih salah satu mode di atas untuk memulai." />}
          {active.map((p) => <JobRow key={p.id} p={p} />)}
        </div>
        <div className="lg:col-span-5 space-y-4">
          <div><p className="tag">Antrean review</p><h2 className="font-serif text-3xl mt-1">Menunggu persetujuan</h2></div>
          {queue.length === 0 && <Empty icon={Film} text="Video yang selesai dirender akan muncul di sini untuk Anda review." />}
          {queue.slice(0, 6).map((v) => <ReviewItem key={v.id} v={v} />)}
        </div>
      </section>

      {recent.length > 0 && (
        <section className="space-y-4">
          <div><p className="tag">Galeri</p><h2 className="font-serif text-3xl mt-1">Karya terbaru</h2></div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {recent.map((p) => (
              <Link key={p.id} to={`/proyek/${p.id}`} className="group relative aspect-[9/16] rounded-xl overflow-hidden border border-[#F3D9A2]/10" data-testid={`recent-project-${p.id}`}>
                <img src={mediaUrl(p.thumb)} alt={p.title} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/90 to-transparent">
                  <p className="text-[11px] text-[#FAF7F2] line-clamp-2">{p.title}</p>
                  <span className={`mt-1 inline-block text-[10px] px-1.5 rounded border ${STATUS[p.status]?.cls}`}>{STATUS[p.status]?.label}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export const Empty = ({ icon: Icon, text }) => (
  <div className="rounded-xl border border-dashed border-[#F3D9A2]/15 p-8 text-center text-sm text-[#7B6F8E]">
    <Icon className="h-6 w-6 mx-auto mb-2 text-[#7B6F8E]" />{text}
  </div>
);
export { ProgressBar };
