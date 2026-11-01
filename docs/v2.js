(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = (v, d = 1) => (v == null ? "–" : (v > 0 ? "+" : "") + v.toFixed(d) + "%");
  const num = (v, d = 2) => (v == null ? "–" : v.toFixed(d));
  const cls = (v) => (v == null ? "" : v > 0.05 ? "up" : v < -0.05 ? "down" : "");
  const PAL = ["#2f5d8a", "#c06a2b", "#7a5aa6", "#3b8f8f", "#a8556f", "#8a7a2f", "#4e6e3a", "#5b5b9a"];
  let D, chart, cur = "oos";
  const SHORT = { trend_sma200d: "Trend (SMA)", tsmom: "Momentum", macd_regime: "MACD+trend", bb_squeeze: "BB squeeze",
    vol_target: "Vol-target", ema_cross: "EMA (live)", rsi_meanrev: "RSI (live)", donchian_breakout: "Donchian (live)" };

  function rankList() {
    const t = D.table;
    $("rank").innerHTML = D.verdicts.map((v) => {
      const m = t[v.id].oos;
      return `<div class="rk"><div class="l1"><span><b>#${v.rank}</b> ${esc(v.label)}</span>
        <span class="pill ${v.pass ? "pass" : "fail"}">${v.pass ? "PASS" : "FAIL"}</span></div>
        <div class="kvs"><span>Return <b class="${cls(m.return_pct)}">${pct(m.return_pct, 0)}</b></span>
        <span>vs HOLD <b class="${cls(v.excess_vs_hold_pct)}">${(v.excess_vs_hold_pct > 0 ? "+" : "") + v.excess_vs_hold_pct.toFixed(0)} pts</b></span>
        <span>Max drop <b>${pct(m.max_dd_pct, 0)}</b></span><span>Sortino <b>${num(m.sortino)}</b></span>
        <span>Calmar <b>${num(m.calmar)}</b></span><span>Trades <b>${m.trades}</b></span></div>
        ${v.pass ? "" : `<div class="reason">${esc(v.reasons.join("; "))}</div>`}</div>`;
    }).join("");
    const h = D.bench.hold.oos, d = D.bench.dca.oos;
    $("passrule").innerHTML = `Benchmarks, same period and costs: <b>HOLD</b> ${pct(h.return_pct, 0)} (max drop ${pct(h.max_dd_pct, 0)}, Sortino ${num(h.sortino)}, Calmar ${num(h.calmar)}) · <b>Weekly DCA</b> ${pct(d.return_pct, 0)} (max drop ${pct(d.max_dd_pct, 0)}).<br>PASS = at least 30 trades, better Sortino AND Calmar than HOLD, and a profit, all out-of-sample.`;
  }

  function regimeTable() {
    $("seg").innerHTML = D.regimes.map(([k, name]) =>
      `<button role="tab" class="${k === cur ? "on" : ""}" data-k="${k}">${esc(name.replace(" (2022 to now)", ""))}</button>`).join("");
    $("seg").querySelectorAll("button").forEach((b) => (b.onclick = () => { cur = b.dataset.k; regimeTable(); }));
    const hold = D.bench.hold[cur];
    const rows = Object.keys(D.table).map((id) => [SHORT[id] || D.labels[id], D.table[id][cur], false])
      .concat([["HOLD", hold, true], ["Weekly DCA", D.bench.dca[cur], true]])
      .filter((r) => r[1]).sort((a, b) => b[1].return_pct - a[1].return_pct);
    const [, name, a, b] = D.regimes.find((r) => r[0] === cur);
    $("regime").innerHTML = `<div class="hint" style="margin:6px 0">${esc(name)}: ${a} to ${b || "now"}</div>
      <table class="rt"><thead><tr><th>Strategy</th><th>Return</th><th>vs HOLD (pts)</th><th>Max drop</th><th>Sortino</th><th>Trades</th></tr></thead><tbody>
      ${rows.map(([n, m, bench]) => `<tr class="${bench ? "bench" : ""}"><td>${esc(n)}</td><td class="${cls(m.return_pct)}">${pct(m.return_pct, 0)}</td>
        <td class="${cls(m.return_pct - hold.return_pct)}">${n === "HOLD" ? "–" : (m.return_pct - hold.return_pct > 0 ? "+" : "") + (m.return_pct - hold.return_pct).toFixed(0)}</td>
        <td>${pct(m.max_dd_pct, 0)}</td><td>${num(m.sortino)}</td><td>${bench ? "–" : m.trades}</td></tr>`).join("")}
      </tbody></table>`;
  }

  function growth() {
    const ids = D.verdicts.slice(0, 4).map((v) => v.id).concat(["hold"]);
    const sets = ids.map((id, i) => ({
      label: id === "hold" ? "HOLD" : D.labels[id], data: (D.curves[id] || []).map(([d, v]) => ({ x: Date.parse(d + "T00:00:00Z"), y: v })),
      borderColor: id === "hold" ? "#6b7280" : PAL[i], borderDash: id === "hold" ? [6, 4] : [], borderWidth: 2, pointRadius: 0, tension: 0,
    }));
    $("legend").innerHTML = sets.map((s) => `<span><span class="swatch" style="background:${s.borderColor}"></span>${esc(s.label)}</span>`).join("");
    if (!window.Chart) return;
    const xs = sets.flatMap((s) => s.data.map((p) => p.x));
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    const f = new Intl.DateTimeFormat("en-IN", { month: "short", year: "2-digit", timeZone: "UTC" });
    chart = new Chart($("chart"), { type: "line", data: { datasets: sets }, options: {
      responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: "nearest", axis: "x", intersect: false },
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: (it) => f.format(new Date(it[0].parsed.x)),
        label: (it) => `${it.dataset.label}: ₹${it.parsed.y.toFixed(0)}` } } },
      scales: { x: { type: "linear", min: xmin, max: xmax, ticks: { callback: (v) => f.format(new Date(v)), maxTicksLimit: 5, maxRotation: 0, color: "#6b7280" }, grid: { color: "#efede7" } },
                y: { type: "logarithmic", ticks: { callback: (v) => "₹" + v, maxTicksLimit: 6, color: "#6b7280" }, grid: { color: "#efede7" } } } } });
  }

  fetch("v2.json?t=" + Date.now()).then((r) => r.json()).then((d) => {
    D = d;
    $("sub").textContent = `8 strategies vs holding BTC and weekly DCA. Data to ${d.data_to}.`;
    $("how").innerHTML = [
      "BTC/USDT hourly candles from June 2020 (Binance public data); 4h candles are built from them.",
      "Walk-forward: each test year (2022, 2023, 2024, 2025, 2026 so far) uses settings tuned only on the years before it. The test years are never used for tuning.",
      `Costs on every trade: ${d.fee_pct}% fee + ${d.slippage_pct}% slippage. Orders fill at the next candle's open. An open position is counted as sold at the end, same as HOLD.`,
      "Max drop = worst fall from a peak. Sortino = return per unit of downside swings. Calmar = yearly return ÷ max drop. Higher is better for both.",
    ].map((s) => `<li>${s}</li>`).join("");
    rankList(); regimeTable(); growth();
  });
})();
