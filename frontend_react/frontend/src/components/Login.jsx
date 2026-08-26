import { useState } from "react";
import { api } from "../api/client";

export default function Login({ onLoggedIn }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("demo1234");
  const [status, setStatus] = useState("");

  async function handleLogin() {
    try {
      const data = await api.login(username, password);
      localStorage.setItem("bs_token", data.access_token);
      setStatus(`Logged in as ${username} (${data.role})`);
      onLoggedIn(data.access_token, data.role);
    } catch (e) {
      setStatus("Login failed: " + e.message);
    }
  }

  return (
    <section>
      <h2 className="text-accent2 border-b border-border pb-1.5 mt-8 text-lg font-semibold">
        1. Login
      </h2>
      <div className="bg-card border border-border rounded-lg p-3.5 my-2">
        <div className="flex gap-2 flex-wrap">
          <input
            className="bg-bg border border-border text-text px-2 py-2 rounded-md"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username (e.g. admin)"
          />
          <input
            className="bg-bg border border-border text-text px-2 py-2 rounded-md"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password"
          />
          <button
            className="bg-primary hover:bg-primaryHover text-white border-none px-3.5 py-2 rounded-md cursor-pointer"
            onClick={handleLogin}
          >
            Login
          </button>
        </div>
        <div className="text-accent2 mt-2">{status}</div>
      </div>
    </section>
  );
}
