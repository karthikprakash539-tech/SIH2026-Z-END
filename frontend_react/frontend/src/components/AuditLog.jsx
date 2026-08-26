import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function AuditLog({ token, role, refreshKey }) {
  const [logs, setLogs] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || role !== "admin") return;
    api
      .getAuditLog()
      .then(setLogs)
      .catch(() => setError("Not authorized (admin only)."));
  }, [token, role, refreshKey]);

  return (
    <section>
      <h2 className="text-accent2 border-b border-border pb-1.5 mt-8 text-lg font-semibold">
        6. Audit Log (admin only)
      </h2>
      <div className="bg-card border border-border rounded-lg p-3.5 my-2">
        {!token || role !== "admin" ? (
          "Login as admin to view."
        ) : error ? (
          error
        ) : !logs ? (
          "Loading..."
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["Action", "Target", "Actor", "Time"].map((h) => (
                  <th key={h} className="text-left px-2 py-1.5 border-b border-border">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="px-2 py-1.5 border-b border-border">{l.action}</td>
                  <td className="px-2 py-1.5 border-b border-border">
                    {l.target_table} #{l.target_id}
                  </td>
                  <td className="px-2 py-1.5 border-b border-border">user {l.actor_id}</td>
                  <td className="px-2 py-1.5 border-b border-border">
                    {new Date(l.timestamp).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
