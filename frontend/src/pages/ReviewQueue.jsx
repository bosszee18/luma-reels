import { useEffect, useState } from "react";
import { Film } from "lucide-react";
import { useApi } from "@/lib/api";
import { ReviewItem, Empty } from "@/pages/Studio";

export default function ReviewQueue() {
  const api = useApi();
  const [list, setList] = useState(null);
  useEffect(() => {
    const load = () => api.get("/review-queue").then((r) => setList(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [api]);
  return (
    <div className="space-y-8 max-w-3xl">
      <div className="rise"><p className="tag">Antrean review</p><h1 className="mt-2 text-4xl sm:text-5xl font-serif tracking-tight">Menunggu persetujuan Anda</h1>
        <p className="mt-3 text-[#B5A9C4]">Putar, revisi bagian tertentu, lalu setujui versi final sebelum dipublikasikan.</p></div>
      {list && list.length === 0 && <Empty icon={Film} text="Tidak ada video yang menunggu review." />}
      <div className="space-y-3" data-testid="review-queue-list">{(list || []).map((v) => <ReviewItem key={v.id} v={v} />)}</div>
    </div>
  );
}
