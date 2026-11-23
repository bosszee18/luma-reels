import { Scissors, Sparkles, Lightbulb } from "lucide-react";

export const MODES = {
  autoclip: {
    key: "autoclip", name: "AutoClip", color: "#D97745", soft: "rgba(217,119,69,0.14)", icon: Scissors,
    badge: "Tembaga • Shorts & Reels",
    desc: "Video panjang + referensi YouTube menjadi hingga 5 klip berbeda dengan hook, konteks, payoff, dan CTA.",
  },
  automotion: {
    key: "automotion", name: "AutoMotion", color: "#A855F7", soft: "rgba(168,85,247,0.14)", icon: Sparkles,
    badge: "Violet • Kinetic & B-roll",
    desc: "Footage mentah dirapikan jedanya, audionya, ritme dan framing — lalu diberi tipografi, motion, dan B-roll.",
  },
  explainer: {
    key: "explainer", name: "Explainer", color: "#10B981", soft: "rgba(16,185,129,0.14)", icon: Lightbulb,
    badge: "Jade • Ide ke storyboard",
    desc: "Ide Hari Ini dari tren Indonesia & global, atau topik sendiri — riset, narasi, visual, suara, jadi video.",
  },
};

export const STATUS = {
  queued: { label: "Antre", cls: "text-[#B5A9C4] border-[#B5A9C4]/30" },
  processing: { label: "Diproduksi", cls: "text-[#F3D9A2] border-[#F3D9A2]/40" },
  review: { label: "Siap Review", cls: "text-[#34D399] border-[#34D399]/40" },
  revising: { label: "Direvisi", cls: "text-[#C084FC] border-[#C084FC]/40" },
  approved: { label: "Disetujui", cls: "text-[#F3D9A2] border-[#F3D9A2]/60 bg-[#F3D9A2]/10" },
  failed: { label: "Gagal", cls: "text-red-300 border-red-400/40" },
  rendering: { label: "Render", cls: "text-[#F3D9A2] border-[#F3D9A2]/40" },
};

export const STYLES = [
  { key: "clay", label: "Clay", hint: "Plastisin stop-motion, hangat & taktil", grad: "from-[#D97745]/40 to-[#F3D9A2]/10" },
  { key: "2d", label: "2D", hint: "Ilustrasi vektor flat, bersih & tegas", grad: "from-[#10B981]/35 to-[#140F1D]" },
  { key: "3d", label: "3D", hint: "Render 3D stilistik, cahaya lembut", grad: "from-[#A855F7]/40 to-[#140F1D]" },
  { key: "realistis", label: "Realistis", hint: "Foto sinematik fotorealistis", grad: "from-[#F3D9A2]/30 to-[#0B080F]" },
];

export const PLATFORMS = [
  { key: "tiktok", label: "TikTok" },
  { key: "instagram", label: "Instagram Reels" },
  { key: "facebook", label: "Facebook Reels" },
  { key: "youtube", label: "YouTube / Shorts" },
];
