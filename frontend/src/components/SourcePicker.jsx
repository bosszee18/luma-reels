import { useEffect, useRef, useState } from "react";
import { UploadCloud, FolderOpen, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import { Checkbox } from "@/components/ui/checkbox";
import { ProgressBar } from "@/components/StageTimeline";

// Upload a new master/footage file or pick one already in the user's storage.
export const SourcePicker = ({ value, onChange, color }) => {
  const api = useApi();
  const inputRef = useRef(null);
  const [tab, setTab] = useState("upload");
  const [rights, setRights] = useState(false);
  const [pct, setPct] = useState(null);
  const [library, setLibrary] = useState([]);
  const [drag, setDrag] = useState(false);

  useEffect(() => { api.get("/assets", { params: { kind: "master" } }).then((r) => setLibrary(r.data)).catch(() => {}); }, [api]);

  const upload = async (file) => {
    if (!file) return;
    if (!rights) return toast.error("Centang konfirmasi hak/izin materi terlebih dahulu.");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("rights_confirmed", "true");
    setPct(0);
    try {
      const r = await api.post("/uploads", fd, { onUploadProgress: (e) => setPct(e.total ? e.loaded / e.total : 0) });
      onChange(r.data);
      setLibrary((l) => [r.data, ...l]);
      toast.success("File tersimpan di penyimpanan Anda");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setPct(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2 text-sm">
        {[["upload", "Unggah file", UploadCloud], ["library", "Dari penyimpanan", FolderOpen]].map(([k, l, I]) => (
          <button key={k} type="button" onClick={() => setTab(k)} data-testid={`source-tab-${k}`}
            className={`px-3 py-1.5 rounded-full border flex items-center gap-1.5 transition-colors ${tab === k ? "border-[#F3D9A2]/50 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>
            <I className="h-3.5 w-3.5" /> {l}
          </button>
        ))}
      </div>
      {tab === "upload" ? (
        <>
          <div data-testid="wizard-file-dropzone" onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files?.[0]); }}
            className="cursor-pointer rounded-2xl border border-dashed p-8 text-center transition-colors"
            style={{ borderColor: drag ? color : "rgba(243,217,162,0.2)", background: drag ? `${color}12` : "rgba(20,15,29,0.6)" }}>
            <UploadCloud className="h-8 w-8 mx-auto" style={{ color }} />
            <p className="mt-3 text-[#FAF7F2]">Seret video ke sini atau klik untuk memilih</p>
            <p className="text-xs text-[#7B6F8E] mt-1">MP4, MOV, M4V, WEBM, MKV • maks. 500 MB</p>
            <input ref={inputRef} type="file" accept="video/*" hidden data-testid="wizard-file-input" onChange={(e) => upload(e.target.files?.[0])} />
          </div>
          {pct !== null && <div className="space-y-1"><ProgressBar value={pct} color={color} testid="upload-progress" /><p className="text-xs text-[#B5A9C4] flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Mengunggah {Math.round(pct * 100)}%</p></div>}
          <label className="flex items-start gap-2 text-sm text-[#B5A9C4]">
            <Checkbox checked={rights} onCheckedChange={(v) => setRights(!!v)} data-testid="rights-confirm-checkbox" className="mt-0.5 border-[#F3D9A2]/40" />
            Saya pemilik materi ini atau memiliki izin untuk mengolah dan mempublikasikannya.
          </label>
        </>
      ) : (
        <div className="grid sm:grid-cols-2 gap-2 max-h-64 overflow-y-auto" data-testid="source-library-list">
          {library.length === 0 && <p className="text-sm text-[#7B6F8E]">Belum ada file di penyimpanan.</p>}
          {library.map((a) => (
            <button key={a.id} type="button" onClick={() => onChange(a)} data-testid={`library-asset-${a.id}`}
              className={`text-left rounded-xl border p-3 text-sm transition-colors ${value?.id === a.id ? "border-[#F3D9A2]/60 bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 hover:border-[#F3D9A2]/30"}`}>
              <p className="text-[#FAF7F2] truncate">{a.filename}</p>
              <p className="text-xs text-[#7B6F8E]">{(a.size / 1048576).toFixed(1)} MB • {new Date(a.created_at).toLocaleDateString("id-ID")}</p>
            </button>
          ))}
        </div>
      )}
      {value && (
        <div className="flex items-center gap-2 text-sm text-[#34D399]" data-testid="selected-source">
          <CheckCircle2 className="h-4 w-4" /> Dipilih: <span className="text-[#FAF7F2] truncate">{value.filename}</span>
        </div>
      )}
    </div>
  );
};
