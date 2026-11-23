export const ScoreRing = ({ score, size = 64, testid }) => {
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const color = s >= 80 ? "#10B981" : s >= 60 ? "#F3D9A2" : "#D97745";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} data-testid={testid || "editorial-score"}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(243,217,162,0.12)" strokeWidth="3" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="3" fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - s / 100)} style={{ transition: "stroke-dashoffset .8s" }} />
      </svg>
      <span className="absolute inset-0 grid place-items-center font-serif text-[#FAF7F2]" style={{ fontSize: size * 0.34 }}>{score == null ? "–" : s}</span>
    </div>
  );
};
