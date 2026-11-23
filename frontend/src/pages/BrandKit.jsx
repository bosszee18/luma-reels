import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { useApi, errMsg } from "@/lib/api";
import { Input } from "@/components/ui/input";

const Row = ({ label, hint, children }) => (
  <div className="grid sm:grid-cols-3 gap-2 sm:gap-6 py-5 border-b border-[#F3D9A2]/8">
    <div><p className="text-sm font-semibold text-[#FAF7F2]">{label}</p>{hint && <p className="text-xs text-[#7B6F8E] mt-1">{hint}</p>}</div>
    <div className="sm:col-span-2">{children}</div>
  </div>
);

const Choice = ({ options, value, onChange, testid }) => (
  <div className="flex flex-wrap gap-2">
    {options.map(([k, l]) => (
      <button key={k} type="button" onClick={() => onChange(k)} data-testid={`${testid}-${k}`}
        className={`px-3.5 py-1.5 rounded-full border text-sm ${value === k ? "border-[#F3D9A2]/60 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{l}</button>
    ))}
  </div>
);

export default function BrandKit() {
  const api = useApi();
  const [b, setB] = useState(null);
  useEffect(() => { api.get("/brand-kit").then((r) => setB(r.data)).catch(() => {}); }, [api]);
  if (!b) return null;
  const set = (k) => (v) => setB({ ...b, [k]: v?.target ? v.target.value : v });
  const save = async () => {
    try {
      const r = await api.put("/brand-kit", b);
      setB(r.data);
      toast.success("Brand Kit disimpan — dipakai di semua render berikutnya.");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <div className="max-w-4xl space-y-6">
      <div className="rise"><p className="tag">Identitas kreator</p><h1 className="mt-2 text-4xl sm:text-5xl font-serif tracking-tight">Brand Kit</h1>
        <p className="mt-3 text-[#B5A9C4]">Warna, suara, musik, CTA, dan watermark yang otomatis diterapkan pada subtitle, hook, dan kartu CTA.</p></div>
      <div className="rounded-2xl border border-[#F3D9A2]/12 bg-[#140F1D]/80 px-6" data-testid="brand-kit-form">
        <Row label="Nama brand"><Input value={b.name} onChange={set("name")} data-testid="brand-name-input" className="bg-[#0B080F]/60" placeholder="mis. Kopi Pagi Studio" /></Row>
        <Row label="Palet" hint="Aksen dipakai untuk highlight subtitle; primer untuk latar hook & CTA.">
          <div className="flex flex-wrap gap-4">
            {[["accent", "Aksen"], ["primary", "Primer"]].map(([k, l]) => (
              <label key={k} className="flex items-center gap-2 text-sm text-[#B5A9C4]">
                <input type="color" value={b[k]} onChange={set(k)} className="h-9 w-12 rounded border border-[#F3D9A2]/20 bg-transparent" data-testid={`brand-${k}-color-input`} />
                {l} <span className="font-mono text-xs">{b[k]}</span>
              </label>
            ))}
            <span className="px-4 py-2 rounded-lg text-sm font-bold" style={{ background: b.primary, color: b.accent }}>Contoh hook</span>
          </div>
        </Row>
        <Row label="Suara narasi" hint="Konsisten di semua adegan Explainer.">
          <Choice options={[["hangat", "Hangat & tenang"], ["sinematik", "Dalam & sinematik"], ["tenang", "Bijak"], ["energik", "Energik"]]} value={b.voice} onChange={set("voice")} testid="brand-voice" />
        </Row>
        <Row label="Mood musik" hint="Latar ambient prosedural yang otomatis merunduk saat ada suara.">
          <Choice options={[["hangat", "Hangat"], ["sinematik", "Sinematik"], ["cerah", "Cerah"], ["tenang", "Tenang"]]} value={b.music_mood} onChange={set("music_mood")} testid="brand-music" />
        </Row>
        <Row label="CTA default"><Input value={b.cta} onChange={set("cta")} maxLength={80} data-testid="brand-cta-input" className="bg-[#0B080F]/60" /></Row>
        <Row label="Watermark" hint="Teks kecil di pojok kiri atas (kosongkan untuk tanpa watermark)."><Input value={b.watermark} onChange={set("watermark")} maxLength={40} data-testid="brand-watermark-input" className="bg-[#0B080F]/60" placeholder="@akunanda" /></Row>
        <Row label="Nada bahasa"><Input value={b.tone} onChange={set("tone")} maxLength={120} data-testid="brand-tone-input" className="bg-[#0B080F]/60" /></Row>
        <div className="py-5">
          <button type="button" onClick={save} data-testid="brand-kit-save-button" className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-[#F3D9A2] text-[#140F1D] font-semibold hover:bg-[#F9EDCE]"><Save className="h-4 w-4" /> Simpan Brand Kit</button>
        </div>
      </div>
    </div>
  );
}
