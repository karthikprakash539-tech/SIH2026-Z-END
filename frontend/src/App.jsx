import { useState } from "react";
import Login from "./components/Login";
import SectionsTable from "./components/SectionsTable";
import DefectsSummary from "./components/DefectsSummary";
import Dashboard from "./components/Dashboard";
import PlansGrid from "./components/PlansGrid";
import AuditLog from "./components/AuditLog";
import NetworkGraph from "./components/NetworkGraph";

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("bs_token") || null);
  const [role, setRole] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  function handleLoggedIn(tok, r) {
    setToken(tok);
    setRole(r);
  }

  function bump() {
    setRefreshKey((k) => k + 1);
  }

  return (
    <div className="min-h-screen bg-bg text-text font-sans p-5">
      <h1 className="text-accent text-2xl font-semibold">BlockSync — Automatic Block Planning</h1>

      <Login onLoggedIn={handleLoggedIn} />

      <NetworkGraph />

      <SectionsTable />
      <DefectsSummary refreshKey={refreshKey} />
      <Dashboard refreshKey={refreshKey} />
      <PlansGrid token={token} role={role} onChanged={bump} />
      <AuditLog token={token} role={role} refreshKey={refreshKey} />
    </div>
  );
}
