import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  const link = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-lg text-sm font-medium ${
      isActive ? "bg-ember text-white" : "text-cream hover:bg-edge"
    }`;

  return (
    <div className="min-h-screen">
      <header className="border-b border-edge sticky top-0 bg-ink/90 backdrop-blur z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="font-display text-2xl font-semibold text-cream">Parallel-AEO</span>
            <span className="text-[10px] font-mono uppercase tracking-widest text-ember">
              AI Visibility Scanner
            </span>
          </div>
          <nav className="flex gap-1">
            <NavLink to="/" end className={link}>
              New Run
            </NavLink>
            <NavLink to="/runs" className={link}>
              Runs
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
