import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Dashboard({ refreshKey }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    api.getDashboard().then(setD).catch(() => setD(null));
  }, [refreshKey]);

  return (
    <section>
      <h2 className="text-accent2 border-b border-border pb-1.5 mt-8 text-lg font-semibold">
        4. Dashboard
      </h2>
      <div className="bg-card border border-border rounded-lg p-3.5 my-2">
        {!d ? (
          "Loading..."
        ) : (
          <div className="flex gap-2 flex-wrap">
            <div>
              Total defects: <b>{d.total_defects}</b>
            </div>
            <div>
              Open defects: <b>{d.open_defects}</b>
            </div>
            <div>
              Block requests: <b>{d.total_requests}</b>
            </div>
            <div>
              Plans generated: <b>{d.plans_generated}</b>
            </div>
            <div>
              Best plan: <b>{d.best_plan || "-"}</b> (score {d.best_plan_score ?? "-"})
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
