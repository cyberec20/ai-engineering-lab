const runBtn = document.getElementById("run");
const resultEl = document.getElementById("result");
const notesEl = document.getElementById("notes");

async function callDesk() {
  resultEl.textContent = "Ejecutando...";
  const payload = {
    symbol: "XAU/USD (broker: GOLD-T)",
    timeframe: "M1",
    notes: notesEl.value || null,
  };
  try {
    const res = await fetch("/api/desk/evaluate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      resultEl.textContent = `Error ${res.status}`;
      return;
    }
    const data = await res.json();
    resultEl.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    resultEl.textContent = err.message;
  }
}

runBtn.addEventListener("click", () => {
  callDesk().catch((err) => {
    resultEl.textContent = err.message;
  });
});
