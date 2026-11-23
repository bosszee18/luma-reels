import { useMemo } from "react";
import axios from "axios";
import { useAuth } from "@clerk/react";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const mediaUrl = (asset, download = false) => {
  if (!asset?.url) return "";
  const u = asset.url.startsWith("http") ? asset.url : `${BACKEND_URL}${asset.url}`;
  return download ? `${u}&download=1` : u;
};

export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Terjadi kesalahan";
  if (typeof d === "string") return d;
  if (d.message) return d.message;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
  return JSON.stringify(d);
};

export function useApi() {
  const { getToken } = useAuth();
  return useMemo(() => {
    const inst = axios.create({ baseURL: API });
    inst.interceptors.request.use(async (c) => {
      const t = await getToken();
      if (t) c.headers.Authorization = `Bearer ${t}`;
      return c;
    });
    return inst;
  }, [getToken]);
}

export async function downloadBlob(api, path, filename) {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const fmtTime = (s) => {
  const n = Math.max(0, Number(s) || 0);
  return `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, "0")}`;
};
