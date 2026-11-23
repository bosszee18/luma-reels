import { NavLink, Link } from "react-router-dom";
import { UserButton } from "@clerk/react";
import { Clapperboard } from "lucide-react";

const NAV = [
  { to: "/", label: "Studio", id: "studio", end: true },
  { to: "/proyek", label: "Proyek", id: "projects" },
  { to: "/review", label: "Antrean Review", id: "review" },
  { to: "/brand-kit", label: "Brand Kit", id: "brandkit" },
  { to: "/publikasi", label: "Publikasi", id: "publish" },
];

export const Layout = ({ children }) => (
  <div className="grain min-h-screen relative">
    <header className="sticky top-0 z-50 backdrop-blur-2xl bg-[#0B080F]/85 border-b border-[#F3D9A2]/12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2.5 shrink-0" data-testid="brand-logo-link">
          <span className="h-8 w-8 rounded-lg grid place-items-center border border-[#F3D9A2]/40 bg-[#F3D9A2]/10 shadow-[0_0_24px_rgba(243,217,162,0.18)]">
            <Clapperboard className="h-4 w-4 text-[#F3D9A2]" />
          </span>
          <span className="font-serif text-xl tracking-tight text-[#FAF7F2]">Luma <em className="text-[#F3D9A2]">Atelier</em></span>
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`nav-item-${n.id}`}
              className={({ isActive }) => `px-3 py-1.5 rounded-full transition-colors ${isActive ? "bg-[#F3D9A2]/12 text-[#F3D9A2]" : "text-[#B5A9C4] hover:text-[#FAF7F2]"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto"><UserButton /></div>
      </div>
      <nav className="md:hidden flex gap-1 overflow-x-auto px-4 pb-2 text-xs">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} data-testid={`mobile-nav-item-${n.id}`}
            className={({ isActive }) => `px-3 py-1.5 rounded-full whitespace-nowrap ${isActive ? "bg-[#F3D9A2]/12 text-[#F3D9A2]" : "text-[#B5A9C4]"}`}>
            {n.label}
          </NavLink>
        ))}
      </nav>
    </header>
    <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">{children}</main>
  </div>
);
