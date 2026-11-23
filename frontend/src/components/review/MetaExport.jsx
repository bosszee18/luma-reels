import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, FileText, FileJson, Save } from "lucide-react";
import { useApi, errMsg, mediaUrl, downloadBlob } from "@/lib/api";
import { PLATFORMS } from "@/lib/modes";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export const MetadataPanel = ({ video, onSaved }) => {
  const api = useApi();
  const [p, setP] = useState("tiktok");
  const [meta, setMeta] = useState(video.metadata || {});
  useEffect(() => setMeta(video.metadata || {}), [video.id, video.metadata]);
  const cur = meta[p] || { title: "", caption: "", hashtags: [] };
  const set = (k, val) => setMeta({ ...meta, [p]: { ...cur, [k]: val } });
  const save = async () => {
    try {
      await api.put(`/videos/${video.id}/metadata`, { metadata: meta });
      toast.success("Metadata disimpan");
      onSaved();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <div className="space-y-3" data-testid="metadata-panel">
      <div className="flex flex-wrap gap-1.5">
        {PLATFORMS.map((x) => (
          <button key={x.key} type="button" onClick={() => setP(x.key)} data-testid={`metadata-tab-${x.key}`}
            className={`px-3 py-1 rounded-full border text-xs ${p === x.key ? "border-[#F3D9A2]/60 text-[#F3D9A2] bg-[#F3D9A2]/10" : "border-[#F3D9A2]/12 text-[#B5A9C4]"}`}>{x.label}</button>
        ))}
      </div>
      <Input value={cur.title || ""} onChange={(e) => set("title", e.target.value)} placeholder="Judul" data-testid="metadata-title-input" className="bg-[#0B080F]/60" />
      <Textarea value={cur.caption || ""} onChange={(e) => set("caption", e.target.value)} rows={4} placeholder="Caption" data-testid="metadata-caption-input" className="bg-[#0B080F]/60" />
      <Input value={(cur.hashtags || []).join(" ")} onChange={(e) => set("hashtags", e.target.value.split(/\s+/).filter(Boolean))} placeholder="#hashtag" data-testid="metadata-hashtags-input" className="bg-[#0B080F]/60" />
      <button type="button" onClick={save} data-testid="metadata-save-button" className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#F3D9A2]/30 text-sm text-[#F3D9A2] hover:bg-[#F3D9A2]/10"><Save className="h-4 w-4" /> Simpan metadata</button>
    </div>
  );
};

export const ExportPanel = ({ video, version }) => {
  const api = useApi();
  if (!version) return null;
  const base = `luma-${video.id.slice(0, 8)}-v${version.n}`;
  const dl = async (kind, name) => {
    try {
      await downloadBlob(api, `/videos/${video.id}/export/${kind}?version=${version.n}`, name);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const cls = "flex items-center gap-2 justify-center px-4 py-2.5 rounded-full border border-[#F3D9A2]/25 text-sm text-[#FAF7F2] hover:border-[#F3D9A2]/60 hover:bg-[#F3D9A2]/5 transition-colors";
  return (
    <div className="grid sm:grid-cols-3 gap-2" data-testid="export-panel">
      <a href={mediaUrl(version.video, true)} className={cls} data-testid="export-download-mp4-button"><Download className="h-4 w-4 text-[#F3D9A2]" /> MP4</a>
      <button type="button" onClick={() => dl("srt", `${base}.srt`)} className={cls} data-testid="export-download-srt-button"><FileText className="h-4 w-4 text-[#F3D9A2]" /> Subtitle SRT</button>
      <button type="button" onClick={() => dl("metadata", `${base}-metadata.json`)} className={cls} data-testid="export-download-json-button"><FileJson className="h-4 w-4 text-[#F3D9A2]" /> Metadata</button>
    </div>
  );
};
