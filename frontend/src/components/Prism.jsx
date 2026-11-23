export const Prism = ({ size = 1 }) => (
  <div className="scene3d relative flex items-center justify-center pointer-events-none" style={{ width: 320 * size, height: 320 * size }} aria-hidden="true" data-testid="hero-3d-prism">
    <div className="orbit" style={{ width: 300 * size, height: 300 * size }} />
    <div className="orbit" style={{ width: 230 * size, height: 230 * size, animationDuration: "20s", animationDirection: "reverse", borderColor: "rgba(168,85,247,.22)" }} />
    <div className="float-slow" style={{ transform: `scale(${size})` }}>
      <div className="prism">
        {["f1", "f2", "f3", "f4", "f5", "f6"].map((f) => <div key={f} className={`face ${f}`} />)}
      </div>
    </div>
  </div>
);
