import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, RefreshCw, Sparkles, ExternalLink, Star } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import { MODES, STYLES } from "@/lib/modes";
import { SourcePicker } from "@/components/SourcePicker";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ModeBadge } from "@/components/ModeCard";

const Field = ({ label, hint, children }) => (
  <div className="space-y-2">
    <p className="text-sm font-semibold text-[#FAF7F2]">{label}</p>
    {hint && <p className="text-xs text-[#7B6F8E] -mt-1">{hint}</p>}
    {children}
  </div>
);

const Pills = ({ options, value, onChange, testid }) => (
  <div className="flex flex-wrap gap-2">
    {options.map(([k, l]) => (
      <button key={k} type="button" onClick={() => onChange(k)} data-testid={`${testid}-${k}`}
        className={`px-3.5 py-1.5 rounded-full border text-sm transition-colors ${value === k ? "border-[#F3D9A2]/60 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4] hover:text-[#FAF7F2]"}`}>{l}</button>
    ))}
  </div>
);

const StylePicker = ({ value, onChange }) => (
  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
    {STYLES.map((s) => (
      <button key={s.key} type="button" onClick={() => onChange(s.key)} data-testid={`style-option-${s.key}`}
        className={`text-left rounded-xl border p-4 bg-gradient-to-br ${s.grad} transition-[transform,border-color] hover:-translate-y-0.5 ${value === s.key ? "border-[#F3D9A2]/70" : "border-[#F3D9A2]/12"}`}>
        <p className="font-serif text-2xl text-[#FAF7F2]">{s.label}</p>
        <p className="text-xs text-[#B5A9C4] mt-1">{s.hint}</p>
      </button>
    ))}
  </div>
);

const TrendIdeas = ({ selected, onSelect }) => {
  const api = useApi();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = async (refresh = false) => {
    setLoading(true);
    try {
      const r = await api.get("/trends", { params: { refresh } });
      setData(r.data);
      const rec = r.data.ideas.find((i) => i.recommended) || r.data.ideas[0];
      if (rec) onSelect(rec);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);
  if (loading && !data) return <div className="flex items-center gap-2 text-sm text-[#B5A9C4] py-6"><Loader2 className="h-4 w-4 animate-spin" /> Membaca sinyal tren Indonesia & global…</div>;
  if (!data) return null;
  return (
    <div className="space-y-3" data-testid="trend-ideas-list">
      <div className="flex items-center justify-between text-xs text-[#7B6F8E]">
        <span data-testid="trend-updated">{data.live ? "Sinyal Google Trends" : "Data tren tidak tersedia — ide evergreen"} • diperbarui {data.fetched_wib}</span>
        <button type="button" onClick={() => load(true)} className="flex items-center gap-1 hover:text-[#F3D9A2]" data-testid="trend-refresh-button"><RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> Segarkan</button>
      </div>
      {data.ideas.map((i, n) => (
        <button key={n} type="button" onClick={() => onSelect(i)} data-testid={`trend-idea-${n}`}
          className={`w-full text-left rounded-xl border p-4 transition-colors ${selected?.title === i.title ? "border-[#10B981]/70 bg-[#10B981]/10" : "border-[#F3D9A2]/12 hover:border-[#F3D9A2]/30 bg-[#140F1D]/60"}`}>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {i.recommended && <span className="flex items-center gap-1 text-[#34D399] font-semibold uppercase tracking-wider"><Star className="h-3 w-3" /> Pilihan AI</span>}
            {i.evergreen ? <span className="px-2 py-0.5 rounded-full border border-[#F3D9A2]/30 text-[#F3D9A2]">Evergreen</span>
              : <span className="px-2 py-0.5 rounded-full border border-[#F3D9A2]/15 text-[#B5A9C4]">{i.region}</span>}
            {i.trend_term && <span className="text-[#7B6F8E]">tren: “{i.trend_term}” {i.traffic && `• ${i.traffic} pencarian`}</span>}
          </div>
          <p className="mt-2 font-serif text-xl text-[#FAF7F2]">{i.title}</p>
          <p className="text-sm text-[#B5A9C4] mt-1">{i.reason}</p>
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-[#7B6F8E]">
            <span>Sumber: {i.source_url ? <a href={i.source_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="text-[#F3D9A2] hover:underline inline-flex items-center gap-0.5">{i.source} <ExternalLink className="h-3 w-3" /></a> : i.source}</span>
            <span>{i.updated_wib}</span>
          </div>
        </button>
      ))}
    </div>
  );
};

export default function NewProject() {
  const { mode } = useParams();
  const m = MODES[mode] || MODES.autoclip;
  const api = useApi();
  const nav = useNavigate();
  const [source, setSource] = useState(null);
  const [yt, setYt] = useState("");
  const [target, setTarget] = useState("5");
  const [maxLen, setMaxLen] = useState("60");
  const [intent, setIntent] = useState("");
  const [title, setTitle] = useState("");
  const [exTab, setExTab] = useState("trend");
  const [idea, setIdea] = useState(null);
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("3d");
  const [voice, setVoice] = useState("hangat");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    let input;
    if (mode === "autoclip") input = { master_asset_id: source?.id, youtube_url: yt.trim() || null, target_clips: +target, max_len: +maxLen };
    else if (mode === "automotion") input = { footage_asset_id: source?.id, intent };
    else input = exTab === "trend" ? { source: "trend", idea, style, voice } : { source: "custom", topic, style, voice };
    setBusy(true);
    try {
      const r = await api.post("/projects", { mode, title, input });
      toast.success("Produksi dimulai — progres tersimpan walau halaman dimuat ulang.");
      nav(`/proyek/${r.data.id}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  const ready = mode === "explainer" ? (exTab === "trend" ? !!idea : topic.trim().length > 5) : !!source;

  return (
    <div className="max-w-3xl space-y-8">
      <div className="rise">
        <ModeBadge mode={mode} />
        <h1 className="mt-3 text-4xl sm:text-5xl font-serif tracking-tight">Proyek {m.name} baru</h1>
        <p className="mt-3 text-[#B5A9C4]">{m.desc}</p>
      </div>
      <div className="rounded-2xl border bg-[#140F1D]/80 p-6 sm:p-8 space-y-7" style={{ borderColor: `${m.color}40` }}>
        {mode !== "explainer" && (
          <Field label="Judul proyek (opsional)"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="mis. Podcast Episode 12" data-testid="wizard-title-input" className="bg-[#0B080F]/60" /></Field>
        )}
        {mode === "autoclip" && (
          <>
            <Field label="URL YouTube (referensi)" hint="Dipakai sebagai konteks judul/kanal. Video tidak diunduh dari YouTube — gunakan file master berizin di bawah.">
              <Input value={yt} onChange={(e) => setYt(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" data-testid="wizard-autoclip-youtube-url-input" className="bg-[#0B080F]/60" />
            </Field>
            <Field label="File master"><SourcePicker value={source} onChange={setSource} color={m.color} /></Field>
            <div className="grid sm:grid-cols-2 gap-6">
              <Field label="Target jumlah klip"><Pills options={[["3", "3"], ["4", "4"], ["5", "5"]]} value={target} onChange={setTarget} testid="target-clips" /></Field>
              <Field label="Durasi maksimal per klip"><Pills options={[["30", "30 dtk"], ["45", "45 dtk"], ["60", "60 dtk"]]} value={maxLen} onChange={setMaxLen} testid="max-len" /></Field>
            </div>
          </>
        )}
        {mode === "automotion" && (
          <>
            <Field label="Footage"><SourcePicker value={source} onChange={setSource} color={m.color} /></Field>
            <Field label="Arahan untuk AI (opsional)" hint="Tujuan video, audiens, atau nuansa yang diinginkan.">
              <Textarea value={intent} onChange={(e) => setIntent(e.target.value)} rows={3} placeholder="mis. Tips produktivitas untuk mahasiswa, nuansa energik" data-testid="wizard-automotion-intent-input" className="bg-[#0B080F]/60" />
            </Field>
          </>
        )}
        {mode === "explainer" && (
          <>
            <Pills options={[["trend", "Ide Hari Ini"], ["custom", "Topik Sendiri"]]} value={exTab} onChange={setExTab} testid="explainer-tab" />
            {exTab === "trend" ? <TrendIdeas selected={idea} onSelect={setIdea} /> : (
              <Field label="Topik dalam satu kalimat">
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="mis. Kenapa harga cabai naik saat musim hujan?" data-testid="explainer-custom-topic-input" className="bg-[#0B080F]/60" />
              </Field>
            )}
            <Field label="Gaya visual"><StylePicker value={style} onChange={setStyle} /></Field>
            <Field label="Suara narasi"><Pills options={[["hangat", "Hangat & tenang"], ["sinematik", "Dalam & sinematik"]]} value={voice} onChange={setVoice} testid="voice-option" /></Field>
          </>
        )}
        <button type="button" onClick={submit} disabled={!ready || busy} data-testid="wizard-submit-generation-button"
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3 rounded-full font-semibold text-[#140F1D] bg-[#F3D9A2] hover:bg-[#F9EDCE] disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Mulai produksi
        </button>
      </div>
    </div>
  );
}
