let sessionId = localStorage.getItem("session_id") || null;
let hitlToken = null;

const el = (id) => document.getElementById(id);
const messages = el("messages");

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg";
  const r = document.createElement("div");
  r.className = "role";
  r.textContent = role;
  const b = document.createElement("div");
  b.className = "bubble " + (role === "user" ? "user" : "assistant");
  b.textContent = text;
  wrap.appendChild(r);
  wrap.appendChild(b);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

function setExecution(resp) {
  el("sessionId").textContent = resp.session_id || "-";
  el("runId").textContent = resp.run_id || "-";
  el("traceId").textContent = resp.trace_id || "-";
  el("status").textContent = resp.status || "-";
  el("summary").textContent = JSON.stringify(resp.execution_summary || [], null, 2);

  const s = el("sources");
  s.innerHTML = "";
  (resp.sources || []).forEach((u) => {
    const a = document.createElement("a");
    a.href = u;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.textContent = u;
    s.appendChild(a);
  });
}

function setHITL(visible) {
  el("hitl").style.display = visible ? "block" : "none";
}

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`${res.status} ${t}`);
  }
  return res.json();
}

async function send() {
  const text = el("message").value.trim();
  if (!text) return;
  el("message").value = "";
  addMessage("user", text);
  setHITL(false);

  const resp = await postJSON("/chat", { message: text, session_id: sessionId });
  sessionId = resp.session_id;
  localStorage.setItem("session_id", sessionId);
  hitlToken = resp.hitl_token;
  setExecution(resp);

  if (resp.status === "NEEDS_HITL") {
    addMessage("assistant", `NEEDS_HITL: ${resp.hitl_notes || "Se requiere aprobación humana."}`);
    setHITL(true);
    return;
  }

  addMessage("assistant", resp.answer || "(sin respuesta)");
}

async function approve(approved) {
  if (!sessionId) return;
  const notes = el("hitlNotes").value.trim() || null;
  const resp = await postJSON("/approve", { session_id: sessionId, approved, notes });
  hitlToken = resp.hitl_token;
  setExecution(resp);

  if (resp.status === "NEEDS_HITL") {
    addMessage("assistant", `NEEDS_HITL: ${resp.hitl_notes || "Se requiere aprobación humana."}`);
    setHITL(true);
    return;
  }

  setHITL(false);
  addMessage("assistant", resp.answer || "(sin respuesta)");
}

el("send").addEventListener("click", () => send().catch((e) => addMessage("assistant", `ERROR: ${e.message}`)));
el("message").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send().catch((err) => addMessage("assistant", `ERROR: ${err.message}`));
});
el("approve").addEventListener("click", () => approve(true).catch((e) => addMessage("assistant", `ERROR: ${e.message}`)));
el("reject").addEventListener("click", () => approve(false).catch((e) => addMessage("assistant", `ERROR: ${e.message}`)));

el("meta").textContent = "Ctrl+Enter para enviar · /chat + /approve · Puerto 8100";

if (sessionId) {
  el("sessionId").textContent = sessionId;
}
