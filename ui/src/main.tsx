import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { api } from "./api";
import Ops from "./pages/Ops";
import Reports from "./pages/Reports";
import ChatPanel from "./components/ChatPanel";

// Basit hash router: #/  ·  #/image/<id>  ·  #/reports
function useHash() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const on = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

function Budget() {
  const [b, setB] = useState<{ spend_usd: number; max_budget_usd: number } | null>(null);
  useEffect(() => {
    const load = () => api.budget().then(setB);
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);
  if (!b) return null;
  return <span className="muted small">LLM bütçe: ${b.spend_usd.toFixed(2)} / ${b.max_budget_usd}</span>;
}

function App() {
  const hash = useHash();
  const [path, query = ""] = hash.split("?");
  const [, route, param] = path.split("/");
  const focusReport = new URLSearchParams(query).get("report");
  const page = route === "reports" ? <Reports key={param ?? ""} initialStatus={param ?? ""} /> : <Ops id={route === "image" && param ? param : null} initialReport={focusReport} />;
  const active = (r: string) => (r === "reports" ? route === "reports" : route !== "reports") ? "active" : "";
  return (
    <>
      <div className="topbar">
        <h1>🛡️ Üs Savunma — Karar Destek</h1>
        <nav>
          <a href="#/" className={active("")}>Operasyon</a>
          <a href="#/reports" className={active("reports")}>Raporlar</a>
        </nav>
        <div className="spacer" />
        <Budget />
      </div>
      {page}
      <ChatPanel />
    </>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
