import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Link2, CheckCircle2, AlertTriangle, KeyRound, XCircle } from "lucide-react";
import { useApi, errMsg } from "@/lib/api";

const PUB_STATUS = { terjadwal: "text-[#F3D9A2]", mengirim: "text-[#C084FC]", terbit: "text-[#34D399]", gagal: "text-red-300", dibatalkan: "text-[#7B6F8E]" };

export default function Publish() {
  const api = useApi();
  const [sp] = useSearchParams();
  const [channels, setChannels] = useState([]);
  const [pubs, setPubs] = useState([]);
  const load = () => Promise.all([api.get("/channels"), api.get("/publications")]).then(([c, p]) => { setChannels(c.data); setPubs(p.data); }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [api]);
  useEffect(() => {
    if (sp.get("connected")) toast.success(`Kanal ${sp.get("connected")} terhubung`);
    if (sp.get("oauth_error")) toast.error(`OAuth gagal: ${sp.get("oauth_error")}`);
  }, [sp]);

  const connect = async (c) => {
    try {
      const r = await api.post(`/channels/${c.platform}/connect`);
      window.location.href = r.data.authorize_url;
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const disconnect = async (c) => { await api.delete(`/channels/${c.platform}`); load(); };
  const cancel = async (id) => { try { await api.post(`/publications/${id}/cancel`); load(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="space-y-10">
      <div className="rise"><p className="tag">Pusat publikasi multi-kanal</p><h1 className="mt-2 text-4xl sm:text-5xl font-serif tracking-tight">Kanal & jadwal tayang</h1>
        <p className="mt-3 max-w-2xl text-[#B5A9C4]">Koneksi lewat OAuth resmi; token disimpan di server. Konten hanya dikirim setelah Anda menyetujui versi, akun, visibilitas, dan waktu tayang. Ekspor manual selalu tersedia.</p></div>
      <div className="grid md:grid-cols-2 gap-4">
        {channels.map((c) => (
          <div key={c.platform} className="rounded-2xl border border-[#F3D9A2]/12 bg-[#140F1D]/80 p-5 space-y-3" data-testid={`channel-card-${c.platform}`}>
            <div className="flex items-center justify-between">
              <p className="font-serif text-2xl">{c.label}</p>
              {c.connected ? <span className="text-xs text-[#34D399] flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" /> {c.account_name || "Terhubung"}</span>
                : c.configured ? <span className="text-xs text-[#F3D9A2]">Siap dihubungkan</span>
                  : <span className="text-xs text-[#D97745] flex items-center gap-1" data-testid={`channel-config-needed-${c.platform}`}><AlertTriangle className="h-3.5 w-3.5" /> Kebutuhan konfigurasi</span>}
            </div>
            {!c.configured && (
              <div className="rounded-lg border border-[#D97745]/30 bg-[#D97745]/8 p-3 text-xs text-[#B5A9C4] space-y-1.5">
                <p className="flex items-center gap-1.5 text-[#FBD5BE]"><KeyRound className="h-3.5 w-3.5" /> Kredensial server: {c.required_env.join(", ")}</p>
                <p>Persetujuan platform: {c.approval}</p>
              </div>
            )}
            {c.connected ? (
              <button type="button" onClick={() => disconnect(c)} className="text-sm text-[#7B6F8E] hover:text-red-300" data-testid={`channel-disconnect-${c.platform}`}>Putuskan</button>
            ) : (
              <button type="button" disabled={!c.configured} onClick={() => connect(c)} data-testid={`channel-oauth-connect-button-${c.platform}`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#F3D9A2]/30 text-sm text-[#F3D9A2] hover:bg-[#F3D9A2]/10 disabled:opacity-40 disabled:cursor-not-allowed">
                <Link2 className="h-4 w-4" /> Hubungkan via OAuth
              </button>
            )}
          </div>
        ))}
      </div>
      <div className="space-y-3">
        <h2 className="font-serif text-3xl">Status per kanal</h2>
        {pubs.length === 0 && <p className="text-sm text-[#7B6F8E]" data-testid="publications-empty">Belum ada jadwal publikasi.</p>}
        {pubs.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-[#F3D9A2]/10 bg-[#1A1426]/60 p-3 text-sm" data-testid={`publication-row-${p.id}`}>
            <span className="text-[#FAF7F2] flex-1 min-w-[160px]">{p.video_title} <span className="text-[#7B6F8E]">v{p.version}</span></span>
            <span className="text-[#B5A9C4]">{p.platform} • {p.visibility}</span>
            <span className="text-[#7B6F8E]">{new Date(p.scheduled_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })} WIB</span>
            <span className={`font-semibold ${PUB_STATUS[p.status]}`}>{p.status}</span>
            {p.error && <span className="text-xs text-red-300 w-full">{p.error}</span>}
            {p.status === "terjadwal" && <button type="button" onClick={() => cancel(p.id)} className="text-[#7B6F8E] hover:text-red-300" data-testid={`publication-cancel-${p.id}`}><XCircle className="h-4 w-4" /></button>}
          </div>
        ))}
      </div>
    </div>
  );
}
