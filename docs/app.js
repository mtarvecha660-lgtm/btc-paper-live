(() => {
  const COLORS = { ema_cross: "#2f5d8a", rsi_meanrev: "#c06a2b", donchian_breakout: "#7a5aa6", hold_btc: "#6b7280" };
  const FALLBACK = ["#2f5d8a", "#c06a2b", "#7a5aa6", "#3b8f8f", "#a8556f"];
  const colorOf = (id, i) => COLORS[id] || FALLBACK[i % FALLBACK.length];
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const utc = (s) => { if (!s) return null; const d = /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? new Date(s) : new Date(s.replace(" ", "T") + "Z"); return isNaN(d) ? null : d; };
  const istFmt = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const ist = (s) => { const d = utc(s); return d ? istFmt.format(d) : "–"; };
  const inr = (v) => "₹" + Math.round(v).toLocaleString("en-IN");
  const usd = (v, d = 2) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
  const cls = (v) => (v > 0.005 ? "up" : v < -0.005 ? "down" : "flat");
  let data = null, chart = null;

  function ago(s) {
    const d = utc(s); if (!d) return "never";
    const m = Math.round((Date.now() - d.getTime()) / 60000);
    if (m < 1) return "just now";
    if (m < 60) return m + " min ago";
    const h = Math.floor(m / 60);
    return h + " h " + (m % 60) + " min ago";
  }

  function renderClock() {
    if (!data) return;
    const t = data.last_tick || {};
    const h = data.health || {};
    const lastOk = h.last_ok_tick_utc ? utc(h.last_ok_tick_utc) : null;
    const okMin = lastOk ? (Date.now() - lastOk.getTime()) / 60000 : Infinity;
    const limit = h.stale_after_minutes || 45;
    $("updated").textContent = "Updated " + ago(data.generated_utc);
    $("dot").className = "dot " + (okMin > limit || (t.status && t.status !== "ok") ? "bad" : "ok");
    const s = $("stale");
    if (okMin > limit) {
      s.hidden = false;
      s.textContent = (lastOk ? `The bot's last good run was ${ago(h.last_ok_tick_utc)}` : "The bot hasn't had a good run yet") +
        (h.consecutive_failures ? ` (${h.consecutive_failures} failed in a row)` : "") + ". Numbers below may be out of date.";
    } else s.hidden = true;
  }

  function metricsRow(a) {
    const m = a.metrics || {}, rate = data.inr_per_usdt;
    const money = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + inr(Math.abs(v) * rate);
    const parts = [];
    if (a.excess_vs_hold_pct != null) parts.push(`vs Hold <b class="${cls(a.excess_vs_hold_pct)}">${pct(a.excess_vs_hold_pct)}</b>`);
    if (a.strategy !== "HOLD") {
      if (m.closed_trades) {
        parts.push(`Profit factor <b>${m.profit_factor_inf ? "∞" : m.profit_factor.toFixed(2)}</b>`);
        parts.push(`Expectancy <b>${money(m.expectancy_usdt)}</b>/trade`);
        parts.push(`Avg win / loss <b>${money(m.avg_win_usdt)}</b> / <b>${money(m.avg_loss_usdt)}</b>`);
        if (m.fees_pct_of_gross != null) parts.push(`Fees <b>${m.fees_pct_of_gross.toFixed(0)}%</b> of gross`);
      } else parts.push(`No closed trades yet`);
    }
    if (m.sortino != null) parts.push(`Sortino <b>${m.sortino.toFixed(2)}</b>`);
    return parts.length ? `<div class="metrics">${parts.map((p) => `<span>${p}</span>`).join("")}</div>` : "";
  }

  function renderMonthly() {
    const months = new Set();
    data.accounts.forEach((a) => Object.keys((a.metrics || {}).monthly_returns_pct || {}).forEach((k) => months.add(k)));
    const ms = [...months].sort().reverse();
    if (!ms.length) { $("monthly").innerHTML = `<div class="empty">No data yet.</div>`; return; }
    const label = (k) => new Date(k + "-01T00:00:00Z").toLocaleString("en-IN", { month: "short", year: "numeric", timeZone: "UTC" });
    const short = { ema_cross: "EMA", rsi_meanrev: "RSI", donchian_breakout: "Donchian", hold_btc: "Hold" };
    $("monthly").innerHTML = `<table><thead><tr><th>Month</th>${data.accounts.map((a) => `<th>${esc(short[a.id] || a.label)}</th>`).join("")}</tr></thead>
      <tbody>${ms.map((k) => `<tr><td>${label(k)}</td>${data.accounts.map((a) => {
        const v = ((a.metrics || {}).monthly_returns_pct || {})[k];
        return v == null ? "<td>–</td>" : `<td class="${cls(v)}">${pct(v)}</td>`; }).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function render() {
    const rate = data.inr_per_usdt;
    $("btc").textContent = data.btc_price ? "$" + usd(data.btc_price, 0) : "–";
    renderClock();

    const ranked = [...data.accounts].sort((a, b) => b.pnl_pct - a.pnl_pct);
    $("cards").innerHTML = data.accounts.map((a, i) => {
      const rank = 1 + data.accounts.filter((x) => x.pnl_pct > a.pnl_pct + 1e-9).length;
      const p = a.position;
      const posTxt = p
        ? `LONG ${p.btc.toFixed(5)} BTC @ $${usd(p.entry, 0)}` + (p.stop ? ` · stop $${usd(p.stop, 0)}` : "") +
          (p.unrealized_pct != null ? ` (${pct(p.unrealized_pct)})` : "")
        : "No position (all cash)";
      const la = a.last_action;
      const lt = a.last_trade;
      const action = la ? `<span class="tag ${esc(la.action)}">${esc(la.action)}</span>${ist(la.time)} IST` : "waiting for the first hourly candle";
      return `<article class="card ${a.id === "hold_btc" ? "hold" : ""}">
        <span class="rank">#${rank}</span>
        <div class="row1"><div class="name"><span class="swatch" style="background:${colorOf(a.id, i)}"></span>${esc(a.label)}</div>
          <span class="pill ${cls(a.pnl_pct)}">${pct(a.pnl_pct)}</span></div>
        <div class="why">${esc(a.why)}</div>
        <div class="eq">${inr(a.equity_inr)}<small>${usd(a.equity_usdt)} USDT</small></div>
        <dl class="kv">
          <dt>Position</dt><dd>${posTxt}${a.pending ? ` · ${esc(a.pending.toUpperCase())} queued for next candle` : ""}${a.halted ? " · paused today (loss limit)" : ""}</dd>
          <dt>Last check</dt><dd>${action}</dd>
          <dt>Trades</dt><dd>${a.trades}${lt ? ` · last ${esc(lt.side)} ${ist(lt.time)}` : ""}</dd>
        </dl>
        ${la ? `<div class="reason">${esc(la.plain || la.reason)}</div>` : ""}
        ${metricsRow(a)}
      </article>`;
    }).join("");

    // chart: every account starts at the same ₹ value, then one point per closed candle, then "now"
    const start = data.meta && data.meta.started;
    const startInr = (data.meta && data.meta.start_inr) || 500000;
    const nowT = utc(data.generated_utc).getTime();
    const sets = data.accounts.map((a, i) => {
      const pts = [];
      const st = utc(a.started || start);
      if (st) pts.push({ x: st.getTime(), y: startInr });
      for (const [t, eq] of (data.equity_series[a.id] || [])) {
        const x = utc(t).getTime();
        if (!pts.length || x > pts[pts.length - 1].x) pts.push({ x, y: eq * rate });
      }
      pts.push({ x: nowT, y: a.equity_inr });
      return {
        label: a.label, data: pts, borderColor: colorOf(a.id, i), backgroundColor: colorOf(a.id, i),
        borderWidth: a.id === "hold_btc" ? 2 : 2.2, borderDash: a.id === "hold_btc" ? [6, 4] : [],
        pointRadius: 0, pointHitRadius: 8, tension: 0.15,
      };
    });
    $("legend").innerHTML = data.accounts.map((a, i) =>
      `<span><span class="swatch" style="background:${colorOf(a.id, i)}"></span>${esc(a.label)}</span>`).join("");
    if (window.Chart) {
      const opts = {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "nearest", axis: "x", intersect: false },
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          title: (it) => istFmt.format(new Date(it[0].parsed.x)) + " IST",
          label: (it) => `${it.dataset.label}: ${inr(it.parsed.y)}` } } },
        scales: {
          x: { type: "linear", grid: { color: "#efede7" }, ticks: { color: "#6b7280", maxTicksLimit: 5, maxRotation: 0,
               callback: (v) => istFmt.format(new Date(v)) } },
          y: { grid: { color: "#efede7" }, ticks: { color: "#6b7280", maxTicksLimit: 6,
               callback: (v) => inr(v) } },
        },
      };
      if (chart) { chart.data.datasets = sets; chart.update(); }
      else chart = new Chart($("chart"), { type: "line", data: { datasets: sets }, options: opts });
    }

    renderMonthly();

    // trades
    $("tradecount").textContent = data.trade_count ? data.trade_count + " total" : "";
    $("trades").innerHTML = data.recent_trades.length ? data.recent_trades.map((t) => `
      <div class="t"><div class="l1"><span><span class="tag ${esc(t.side)}">${esc(t.side)}</span><b>${esc(t.account)}</b></span>
        <span class="when">${ist(t.time)} IST</span></div>
        <div class="l1"><span>${usd(t.qty, 5)} BTC @ $${usd(t.price, 0)} · ${inr(t.value * rate)}</span>
        ${t.pnl != null ? `<span class="${cls(t.pnl)}" style="color:var(--${t.pnl >= 0 ? "up" : "down"})">${t.pnl >= 0 ? "+" : "−"}${inr(Math.abs(t.pnl) * rate)}</span>` : ""}</div>
        <div class="reason">${esc(t.reason)}</div></div>`).join("")
      : `<div class="empty">No strategy trades yet. Each one only trades when its signal fires on an hourly candle, which can take hours or days. Their latest decisions are on the cards above.</div>`;

    // ticks
    $("tickhint").textContent = `${data.ticks_ok_24h} of last ${data.ticks_24h} ok`;
    $("ticks").innerHTML = (data.recent_ticks || []).map((t) => `
      <div class="k"><span>${ist(t.time_utc)}</span><span class="st-${esc(t.status)}">${esc(t.status)}</span>
      <span>${t.btc_price ? "$" + usd(+t.btc_price, 0) : "–"}</span></div>
      ${t.note ? `<div class="reason">${esc(t.note)}</div>` : ""}`).join("");

    const m = data.meta || {};
    $("ratenote").innerHTML = m.inr_per_usdt_at_start
      ? `₹ values use 1 USDT = ₹${m.inr_per_usdt_at_start} (rate when the bot started, ${ist(m.started)} IST), so % and ₹ always match.`
      : "";
  }

  async function load() {
    try {
      const r = await fetch("data/summary.json?t=" + Date.now(), { cache: "no-store" });
      data = await r.json();
      render();
    } catch (e) {
      $("updated").textContent = "Couldn’t load data, retrying…";
      $("dot").className = "dot bad";
    }
  }
  load();
  setInterval(load, 120000);
  setInterval(renderClock, 30000);
})();
