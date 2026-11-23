import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, RotateCcw, Info, ArrowLeft, Youtube, Loader2 } from "lucide-react";
import { useApi, errMsg, mediaUrl, fmtTime } from "@/lib/api";
import { MODES, STATUS } from "@/lib/modes";
import { ModeBadge } from "@/components/ModeCard";
import { StageTimeline, ProgressBar } from "@/components/StageTimeline";
import { ScoreRing } from "@/components/ScoreRing";
import { ScorePanel, RevisePanel } from "@/components/review/ScoreRevise";
import { MetadataPanel, ExportPanel } from "@/components/review/MetaExport";
import { PublishDialog } from "@/components/review/PublishDialog";

const TABS = [["skor", "Skor"], ["revisi", "Revisi"], ["metadata", "Metadata"], ["ekspor", "Ekspor"], ["rencana", "Rencana"]];

const PlanView = ({ plan }) => (
  <div className="space-y-3 text-sm" data-testid="plan-panel">
    {plan.hook && <p><span className="tag mr-2">Hook</span><span className="text-[#FAF7F2]">{plan.hook}</span></p>}
    {plan.context && <p><span className="tag mr-2">Konteks</span><span className="text-[#B5A9C4]">{plan.context}</span></p>}
    {plan.payoff && <p><span className="tag mr-2">Payoff</span><span className="text-[#B5A9C4]">{plan.payoff}</span></p>}
    {plan.cta && <p><span className="tag mr-2">CTA</span><span className="text-[#FAF7F2]">{plan.cta}</span></p>}
    {plan.start != null && <p className="text-[#7B6F8E]">Segmen master {fmtTime(plan.start)}–{fmtTime(plan.end)} • crop subjek x={plan.crop_x}</p>}
    {plan.removed_seconds != null && <p className="text-[#7B6F8E]">{plan.removed_seconds} dtk jeda dipangkas • {plan.keep?.length} potongan</p>}
    {plan.scenes && (
      <div className="space-y-2">
        <p className="tag">Storyboard • gaya {plan.style}</p>
        {plan.scenes.map((s, i) => (
          <div key={i} className="flex gap-3 rounded-lg border border-[#F3D9A2]/10 p-2" data-testid={`storyboard-scene-${i + 1}`}>
            {s.image && <img src={mediaUrl(s.image)} alt="" className="h-20 w-14 rounded object-cover shrink-0" />}
            <div><p className="text-xs text-[#F3D9A2]">Adegan {i + 1} • {s.dur ? `${s.dur} dtk` : ""}</p><p className="text-[#B5A9C4]">{s.narration}</p></div>
          </div>
        ))}
      </div>
    )}
    {plan.broll?.length > 0 && (
      <div className="flex gap-2 flex-wrap">
        {plan.broll.map((b, i) => b.image && <img key={i} src={mediaUrl(b.image)} alt={b.prompt} title={b.prompt} className="h-24 w-16 rounded object-cover border border-[#F3D9A2]/10" />)}
      </div>
    )}
  </div>
);

const Review = ({ project, videoId, setVideoId, reload }) => {
  const api = useApi();
  const vRef = useRef(null);
  const videos = project.videos;
  const video = videos.find((v) => v.id === videoId) || videos[0];
  const [verN, setVerN] = useState(null);
  const [tab, setTab] = useState("skor");
  const latest = video?.versions[video.versions.length - 1];
  useEffect(() => setVerN(null), [video?.id, latest?.n]);
  if (!video) return null;
  const version = video.versions.find((x) => x.n === verN) || latest;
  const m = MODES[project.mode];

  const approve = async () => {
    try {
      await api.post(`/videos/${video.id}/approve`, { version: version.n });
      toast.success(`Versi v${version.n} disetujui sebagai final`);
      reload();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const unapprove = async () => { await api.post(`/videos/${video.id}/unapprove`); reload(); };
  const seek = (t) => { if (vRef.current) { vRef.current.currentTime = t; vRef.current.play().catch(() => {}); } };

  return (
    <div className="grid lg:grid-cols-12 gap-6 items-start">
      {videos.length > 1 && (
        <div className="lg:col-span-3 space-y-2 order-2 lg:order-1" data-testid="clip-list">
          <p className="tag">Diurutkan menurut skor</p>
          {videos.map((v, i) => {
            const lv = v.versions[v.versions.length - 1];
            return (
              <button key={v.id} type="button" onClick={() => setVideoId(v.id)} data-testid="review-clip-card-item"
                className={`w-full flex gap-3 items-center text-left rounded-xl border p-2.5 transition-colors ${v.id === video.id ? "bg-[#1A1426]" : "border-[#F3D9A2]/10 hover:border-[#F3D9A2]/30"}`}
                style={v.id === video.id ? { borderColor: m.color } : {}}>
                <span className="font-serif text-lg text-[#7B6F8E] w-5">{i + 1}</span>
                <div className="h-16 w-9 rounded bg-[#0B080F] overflow-hidden shrink-0">{lv?.thumb && <img src={mediaUrl(lv.thumb)} alt="" className="h-full w-full object-cover" />}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#FAF7F2] line-clamp-2">{v.title}</p>
                  <p className={`text-[10px] mt-0.5 ${v.approved_version ? "text-[#F3D9A2]" : "text-[#7B6F8E]"}`}>{v.approved_version ? `Final v${v.approved_version}` : STATUS[v.status]?.label}</p>
                </div>
                <ScoreRing score={v.score} size={38} />
              </button>
            );
          })}
        </div>
      )}
      <div className={`${videos.length > 1 ? "lg:col-span-4" : "lg:col-span-5"} order-1 lg:order-2 space-y-3`}>
        <div className="rounded-2xl overflow-hidden border bg-black mx-auto max-w-[380px] aspect-[9/16]" style={{ borderColor: `${m.color}55` }} data-testid="review-video-player-container">
          {version ? <video key={version.video?.id} ref={vRef} src={mediaUrl(version.video)} poster={mediaUrl(version.thumb)} controls playsInline className="h-full w-full object-contain" data-testid="review-video-player" />
            : <div className="h-full grid place-items-center text-[#7B6F8E] text-sm"><Loader2 className="h-5 w-5 animate-spin" /></div>}
        </div>
        <div className="flex flex-wrap gap-1.5 justify-center" data-testid="version-list">
          {video.versions.map((x) => (
            <button key={x.n} type="button" onClick={() => setVerN(x.n)} title={x.note} data-testid={`version-button-${x.n}`}
              className={`px-3 py-1 rounded-full border text-xs ${x.n === version?.n ? "border-[#F3D9A2]/60 text-[#F3D9A2]" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>
              v{x.n}{video.approved_version === x.n && " ✓"}
            </button>
          ))}
        </div>
        {version && <p className="text-xs text-center text-[#7B6F8E]" data-testid="version-note">{version.note} • {version.duration} dtk • {version.caption_count} baris subtitle</p>}
      </div>
      <div className={`${videos.length > 1 ? "lg:col-span-5" : "lg:col-span-7"} order-3 space-y-5`}>
        <div>
          <h2 className="font-serif text-3xl text-[#FAF7F2]" data-testid="review-video-title">{video.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {video.approved_version === version?.n ? (
              <button type="button" onClick={unapprove} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#F3D9A2]/15 border border-[#F3D9A2]/50 text-[#F3D9A2] text-sm" data-testid="review-approved-state">
                <CheckCircle2 className="h-4 w-4" /> Final disetujui (batalkan)
              </button>
            ) : (
              <button type="button" onClick={approve} disabled={!version || video.status === "revising"} data-testid="review-approve-final-version-button"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#F3D9A2] text-[#140F1D] font-semibold text-sm hover:bg-[#F9EDCE] disabled:opacity-40">
                <CheckCircle2 className="h-4 w-4" /> Setujui v{version?.n} sebagai final
              </button>
            )}
            <PublishDialog video={video} />
          </div>
        </div>
        <div className="flex gap-1 border-b border-[#F3D9A2]/10 overflow-x-auto">
          {TABS.map(([k, l]) => (
            <button key={k} type="button" onClick={() => setTab(k)} data-testid={`review-tab-${k}`}
              className={`px-3 py-2 text-sm -mb-px border-b-2 whitespace-nowrap ${tab === k ? "border-[#F3D9A2] text-[#F3D9A2]" : "border-transparent text-[#B5A9C4]"}`}>{l}</button>
          ))}
        </div>
        <div className="rounded-2xl border border-[#F3D9A2]/10 bg-[#140F1D]/70 p-5">
          {tab === "skor" && <ScorePanel video={video} version={version} onSeek={seek} />}
          {tab === "revisi" && <RevisePanel video={video} getTime={() => vRef.current?.currentTime || 0} onQueued={reload} />}
          {tab === "metadata" && <MetadataPanel video={video} onSaved={reload} />}
          {tab === "ekspor" && <ExportPanel video={video} version={version} />}
          {tab === "rencana" && <PlanView plan={video.plan} />}
        </div>
      </div>
    </div>
  );
};

export default function ProjectDetail() {
  const { id } = useParams();
  const [sp, setSp] = useSearchParams();
  const api = useApi();
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const load = useCallback(async () => {
    try {
      setP((await api.get(`/projects/${id}`)).data);
    } catch (e) {
      setErr(errMsg(e));
    }
  }, [api, id]);
  const busy = p && (["queued", "processing"].includes(p.status) || p.videos?.some((v) => v.status === "revising" || v.status === "rendering"));
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [busy, load]);

  if (err) return <p className="text-red-300" data-testid="project-error">{err}</p>;
  if (!p) return <div className="flex items-center gap-2 text-[#B5A9C4]"><Loader2 className="h-4 w-4 animate-spin" /> Memuat proyek…</div>;
  const m = MODES[p.mode];
  const retry = async () => { await api.post(`/projects/${id}/retry`); load(); };
  const hasVideos = p.videos?.some((v) => v.versions.length);

  return (
    <div className="space-y-8">
      <div className="rise">
        <Link to="/proyek" className="text-sm text-[#7B6F8E] hover:text-[#F3D9A2] inline-flex items-center gap-1" data-testid="back-to-projects-link"><ArrowLeft className="h-4 w-4" /> Proyek</Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <ModeBadge mode={p.mode} />
          <span className={`text-xs px-2.5 py-1 rounded-full border ${STATUS[p.status]?.cls}`} data-testid="project-status">{STATUS[p.status]?.label}</span>
        </div>
        <h1 className="mt-3 text-4xl sm:text-5xl font-serif tracking-tight" data-testid="project-title">{p.title}</h1>
        {p.info?.youtube_ref && <p className="mt-2 text-sm text-[#B5A9C4] flex items-center gap-1.5"><Youtube className="h-4 w-4 text-[#D97745]" /> Referensi: {p.info.youtube_ref.title} — {p.info.youtube_ref.author}</p>}
      </div>

      {(busy && !hasVideos) || p.status === "failed" || ["queued", "processing"].includes(p.status) ? (
        <div className="grid lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 rounded-2xl border bg-[#140F1D]/80 p-6" style={{ borderColor: `${m.color}40` }} data-testid="production-progress-panel">
            <div className="flex items-end justify-between mb-4">
              <div><p className="tag">Progres tahap nyata</p><p className="text-sm text-[#B5A9C4] mt-1">Tersimpan di server — aman untuk memuat ulang halaman.</p></div>
              <span className="font-serif text-5xl text-[#F3D9A2]" data-testid="project-progress-percent">{Math.round(p.progress * 100)}%</span>
            </div>
            <ProgressBar value={p.progress} color={m.color} testid="project-progress-bar" />
            <div className="mt-6"><StageTimeline stages={p.stages} color={m.color} /></div>
            {p.status === "failed" && (
              <div className="mt-6 rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200" data-testid="project-failed-panel">
                {p.error}
                <button type="button" onClick={retry} className="mt-3 flex items-center gap-2 text-[#F3D9A2]" data-testid="project-retry-button"><RotateCcw className="h-4 w-4" /> Ulangi dari tahap gagal</button>
              </div>
            )}
          </div>
          {p.info?.research && (
            <div className="lg:col-span-5 rounded-2xl border border-[#F3D9A2]/10 bg-[#140F1D]/60 p-6 text-sm space-y-2" data-testid="research-panel">
              <p className="tag">Riset</p>
              <p className="text-[#B5A9C4]">{p.info.research.summary}</p>
              <ul className="list-disc pl-5 text-[#B5A9C4] space-y-1">{(p.info.research.key_facts || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
            </div>
          )}
        </div>
      ) : null}

      {p.info?.count_reason && (
        <div className="rounded-xl border border-[#D97745]/40 bg-[#D97745]/10 p-4 text-sm text-[#FBD5BE] flex gap-2" data-testid="clip-count-reason">
          <Info className="h-4 w-4 shrink-0 mt-0.5" /> <span><b>{p.info.clip_count} klip</b> dihasilkan. {p.info.count_reason}</span>
        </div>
      )}
      {hasVideos && <Review project={p} videoId={sp.get("video")} setVideoId={(v) => setSp({ video: v })} reload={load} />}
    </div>
  );
}
