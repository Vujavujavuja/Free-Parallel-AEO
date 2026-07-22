import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  const link = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-lg text-sm font-medium ${
      isActive ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-edge"
    }`;

  return (
    <div className="min-h-screen">
      <header className="border-b border-edge sticky top-0 bg-ink/90 backdrop-blur z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">Free-Parallel-AEO</span>
            <span className="text-xs text-slate-500">AI brand-visibility scanner</span>
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
