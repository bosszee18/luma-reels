import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { MODES } from "@/lib/modes";

export const ModeCard = ({ mode, index = 0 }) => {
  const m = MODES[mode];
  const Icon = m.icon;
  return (
    <Link to={`/baru/${mode}`} data-testid={`mode-card-${mode}-button`}
      className="group relative rise rounded-2xl border p-6 overflow-hidden bg-[#140F1D] transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-1"
      style={{ borderColor: `${m.color}4D`, animationDelay: `${index * 90}ms` }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = `0 10px 40px ${m.color}38`)}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "none")}>
      <div className="absolute -top-16 -right-16 h-48 w-48 rounded-full blur-3xl opacity-40 transition-opacity group-hover:opacity-70" style={{ background: m.color }} />
      <div className="relative flex items-start justify-between">
        <span className="h-11 w-11 rounded-xl grid place-items-center border" style={{ borderColor: `${m.color}66`, background: m.soft }}>
          <Icon className="h-5 w-5" style={{ color: m.color }} />
        </span>
        <ArrowUpRight className="h-5 w-5 text-[#7B6F8E] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-[#FAF7F2]" />
      </div>
      <p className="relative mt-6 text-[11px] uppercase tracking-[0.2em] font-semibold" style={{ color: m.color }}>{m.badge}</p>
      <h3 className="relative mt-1 font-serif text-3xl text-[#FAF7F2]">{m.name}</h3>
      <p className="relative mt-3 text-sm text-[#B5A9C4] leading-relaxed">{m.desc}</p>
    </Link>
  );
};

export const ModeBadge = ({ mode }) => {
  const m = MODES[mode];
  if (!m) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.18em] font-semibold px-2.5 py-1 rounded-full border"
      style={{ color: m.color, borderColor: `${m.color}55`, background: m.soft }} data-testid="mode-badge">
      <m.icon className="h-3 w-3" /> {m.name}
    </span>
  );
};
