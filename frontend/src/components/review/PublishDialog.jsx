import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Send, AlertTriangle, Loader2 } from "lucide-react";
import { useApi, errMsg } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";

export const PublishDialog = ({ video }) => {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [channels, setChannels] = useState([]);
  const [platform, setPlatform] = useState(null);
  const [visibility, setVisibility] = useState("private");
  const [when, setWhen] = useState("now");
  const [at, setAt] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const approved = video.approved_version;

  useEffect(() => {
    if (open) api.get("/channels").then((r) => setChannels(r.data)).catch(() => {});
  }, [open, api]);
  const ch = channels.find((c) => c.platform === platform);

  const submit = async () => {
    setBusy(true);
    try {
      await api.post("/publications", {
        video_id: video.id, version: approved, platform, visibility, confirm,
        scheduled_at: when === "now" ? null : new Date(at).toISOString(),
      });
      toast.success("Publikasi dijadwalkan. Lacak statusnya di halaman Publikasi.");
      setOpen(false);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button type="button" disabled={!approved} data-testid="open-publish-dialog-button"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-[#F3D9A2]/30 text-sm text-[#FAF7F2] hover:bg-[#F3D9A2]/10 disabled:opacity-40 disabled:cursor-not-allowed">
          <Send className="h-4 w-4 text-[#F3D9A2]" /> Kirim / jadwalkan
        </button>
      </DialogTrigger>
      <DialogContent className="bg-[#140F1D] border-[#F3D9A2]/20 max-w-lg" data-testid="publish-dialog">
        <DialogHeader><DialogTitle className="font-serif text-2xl">Publikasikan versi v{approved}</DialogTitle></DialogHeader>
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-2">
            {channels.map((c) => (
              <button key={c.platform} type="button" onClick={() => setPlatform(c.platform)} data-testid={`publish-channel-${c.platform}`}
                className={`text-left rounded-xl border p-3 ${platform === c.platform ? "border-[#F3D9A2]/60 bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12"}`}>
                <p className="text-[#FAF7F2]">{c.label}</p>
                <p className={`text-xs ${c.connected ? "text-[#34D399]" : "text-[#D97745]"}`}>{c.connected ? `Terhubung: ${c.account_name || "akun"}` : c.configured ? "Belum terhubung" : "Kebutuhan konfigurasi"}</p>
              </button>
            ))}
          </div>
          {ch && !ch.connected && (
            <div className="rounded-lg border border-[#D97745]/40 bg-[#D97745]/10 p-3 text-xs text-[#FBD5BE] flex gap-2" data-testid="publish-config-needed">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{ch.configured ? "Hubungkan akun via OAuth di halaman " : "Kredensial aplikasi resmi belum dipasang di server. Lihat "}<Link to="/publikasi" className="underline">Publikasi</Link>. Sementara itu gunakan ekspor MP4 manual.</span>
            </div>
          )}
          <div className="flex gap-2">
            {[["public", "Publik"], ["unlisted", "Terbatas"], ["private", "Privat"]].map(([k, l]) => (
              <button key={k} type="button" onClick={() => setVisibility(k)} data-testid={`publish-visibility-${k}`}
                className={`px-3 py-1.5 rounded-full border text-xs ${visibility === k ? "border-[#F3D9A2]/60 text-[#F3D9A2]" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{l}</button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {[["now", "Sekarang"], ["later", "Jadwalkan"]].map(([k, l]) => (
              <button key={k} type="button" onClick={() => setWhen(k)} data-testid={`publish-when-${k}`}
                className={`px-3 py-1.5 rounded-full border text-xs ${when === k ? "border-[#F3D9A2]/60 text-[#F3D9A2]" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{l}</button>
            ))}
            {when === "later" && <Input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} className="w-auto bg-[#0B080F]/60" data-testid="publish-datetime-input" />}
          </div>
          <label className="flex items-start gap-2 text-[#B5A9C4]">
            <Checkbox checked={confirm} onCheckedChange={(v) => setConfirm(!!v)} className="mt-0.5 border-[#F3D9A2]/40" data-testid="publish-confirm-checkbox" />
            Saya menyetujui versi v{approved}, akun {ch?.account_name || ch?.label || "—"}, visibilitas {visibility}, dan waktu tayang {when === "now" ? "sekarang" : at || "—"}.
          </label>
          <button type="button" onClick={submit} disabled={!ch?.connected || !confirm || busy || (when === "later" && !at)} data-testid="publish-schedule-post-button"
            className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-full bg-[#F3D9A2] text-[#140F1D] font-semibold disabled:opacity-40">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Konfirmasi publikasi
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
