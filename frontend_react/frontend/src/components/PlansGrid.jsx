import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function PlansGrid({ token, role, onChanged }) {
  const [plans, setPlans] = useState(null);
  const [status, setStatus] = useState("");
  const [regenStatus, setRegenStatus] = useState("");

  async function load() {
    try {
      setPlans(await api.getPlans());
    } catch {
      setPlans([]);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function decide(planId, action) {
    if (!token) {
      setStatus("Please login first.");
      setTimeout(() => setStatus(""), 4000);
      return;
    }
    try {
      await api.decidePlan(planId, action);
      setStatus(`Plan ${planId} ${action}d successfully.`);
      onChanged?.();
    } catch (e) {
      setStatus("Action failed: " + e.message);
    }
    setTimeout(() => setStatus(""), 4000);
  }

  async function regenerate() {
    setRegenStatus(" Re-optimizing... (this calls OR-Tools live)");
    try {
      const sections = await api.getSections();
      const randomSection = sections[Math.floor(Math.random() * sections.length)];
      const data = await api.addEmergencyDefect({
        department: ["TMS", "SMMS", "TDMS"][Math.floor(Math.random() * 3)],
        section_id: randomSection.id,
        defect_type: "Emergency defect (simulated live)",
        severity: 5,
      });
      setRegenStatus(` Done — ${data.message}`);
      await load();
      onChanged?.();
    } catch (e) {
      setRegenStatus(" Failed: " + e.message);
    }
  }

  const bestScore = plans && plans.length ? Math.max(...plans.map((p) => p.overall_score)) : null;

  return (
    <section>
      <h2 className="text-accent2 border-b border-border pb-1.5 mt-8 text-lg font-semibold">
        5. AI-Generated Plans (Plan A / B / C)
      </h2>
      <div className="bg-card border border-border rounded-lg p-3.5 my-2">
        <button
          className="bg-primary hover:bg-primaryHover text-white border-none px-3.5 py-2 rounded-md cursor-pointer"
          onClick={regenerate}
        >
          🔥 Simulate Emergency Defect &amp; Re-Optimize Live
        </button>
        <span className="ml-2">{regenStatus}</span>
      </div>

      {status && <div className="text-warn">{status}</div>}

      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        {plans === null ? (
          "Loading..."
        ) : plans.length === 0 ? (
          <div className="bg-card border border-border rounded-lg p-3.5">
            No plans yet — run optimize.py first.
          </div>
        ) : (
          plans.map((p) => {
            const isBest = p.overall_score === bestScore;
            return (
              <div
                key={p.id}
                className={`bg-card border rounded-lg p-3.5 ${
                  isBest ? "border-2 border-accent" : "border-border"
                }`}
              >
                <h3 className="text-base font-semibold">
                  {p.plan_label} {isBest && <span className="badge">BEST</span>}
                </h3>
                <div>Strategy: {p.strategy}</div>
                <div>Completion rate: {p.completion_rate}%</div>
                <div>Total delay: {p.total_delay_minutes} min</div>
                <div>Asset availability: {p.asset_availability}%</div>
                <div>Block utilization: {p.block_utilization}%</div>
                <div>
                  <b>Overall score: {p.overall_score}</b>
                </div>
                <div className="flex gap-2 mt-2.5">
                  <button
                    className="bg-primary hover:bg-primaryHover text-white border-none px-3.5 py-2 rounded-md cursor-pointer"
                    onClick={() => decide(p.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="bg-danger hover:bg-dangerHover text-white border-none px-3.5 py-2 rounded-md cursor-pointer"
                    onClick={() => decide(p.id, "reject")}
                  >
                    Reject
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
