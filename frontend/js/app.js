const TOKEN_KEY = "rpi_monitor_token";
const MAX_POINTS = 40;

const $ = (id) => document.getElementById(id);

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setToken(t) {
  localStorage.setItem(TOKEN_KEY, t);
}

function fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return "--";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function fmtRate(bytesPerSec) {
  if (bytesPerSec === null || bytesPerSec === undefined) return "--";
  return `${fmtBytes(bytesPerSec)}/s`;
}

function fmtUptime(seconds) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

function barClass(percent) {
  if (percent >= 90) return "danger";
  if (percent >= 75) return "warn";
  return "";
}

const AXIS_TITLE_STYLE = { display: true, color: "#93a3bd", font: { size: 11 } };

function makeLineChart(ctx, label, color, unit, yMax) {
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label,
          data: [],
          borderColor: color,
          backgroundColor: color + "33",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          display: true,
          title: { ...AXIS_TITLE_STYLE, text: "Hora" },
          ticks: { color: "#93a3bd", maxTicksLimit: 6 },
          grid: { display: false },
        },
        y: {
          min: 0,
          max: yMax,
          title: { ...AXIS_TITLE_STYLE, text: unit },
          ticks: { color: "#93a3bd" },
          grid: { color: "#22304a" },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function makeBarChart(ctx, label, color, unit) {
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          label,
          data: [],
          backgroundColor: color,
          borderRadius: 4,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { ...AXIS_TITLE_STYLE, text: "Día" },
          ticks: { color: "#93a3bd" },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          title: { ...AXIS_TITLE_STYLE, text: unit },
          ticks: { color: "#93a3bd", precision: 0 },
          grid: { color: "#22304a" },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function pushPoint(chart, label, value) {
  chart.data.labels.push(label);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update("none");
}

const cpuChart = makeLineChart($("cpu-chart"), "CPU %", "#22c55e", "%", 100);
const memChart = makeLineChart($("mem-chart"), "Memoria %", "#3b82f6", "%", 100);
const tempChart = makeLineChart($("temp-chart"), "Temp °C", "#f59e0b", "°C", undefined);
const accessChart = makeBarChart($("access-chart"), "Accesos", "#a855f7", "N° de accesos");

function renderSnapshot(data) {
  const time = new Date(data.timestamp).toLocaleTimeString();

  $("cpu-percent").textContent = `${data.cpu.percent.toFixed(1)}%`;
  $("cpu-load").textContent = `carga: ${data.cpu.load_avg_1m?.toFixed(2) ?? "--"} / ${data.cpu.load_avg_5m?.toFixed(2) ?? "--"} / ${data.cpu.load_avg_15m?.toFixed(2) ?? "--"}`;
  pushPoint(cpuChart, time, data.cpu.percent);

  $("mem-percent").textContent = `${data.memory.percent.toFixed(1)}%`;
  $("mem-detail").textContent = `${fmtBytes(data.memory.used_bytes)} / ${fmtBytes(data.memory.total_bytes)}`;
  pushPoint(memChart, time, data.memory.percent);

  if (data.temperature_c !== null) {
    $("temp-value").textContent = `${data.temperature_c.toFixed(1)}°C`;
    $("temp-status").textContent = data.temperature_c >= 75 ? "⚠️ Alta" : "Normal";
    pushPoint(tempChart, time, data.temperature_c);
  } else {
    $("temp-value").textContent = "N/D";
  }

  $("uptime-value").textContent = fmtUptime(data.uptime_seconds);
  $("boot-time").textContent = `desde ${new Date(data.boot_time).toLocaleString()}`;

  const diskList = $("disk-list");
  diskList.innerHTML = "";
  for (const disk of data.disks) {
    const row = document.createElement("div");
    row.className = "disk-row";
    row.innerHTML = `
      <div style="flex:1">
        <div>${disk.mountpoint} <span style="color:var(--muted)">(${disk.fstype})</span></div>
        <div class="bar ${barClass(disk.percent)}"><div style="width:${disk.percent}%"></div></div>
      </div>
      <div style="text-align:right; margin-left:12px">
        <div>${disk.percent.toFixed(1)}%</div>
        <div style="color:var(--muted); font-size:0.75rem">${fmtBytes(disk.used_bytes)} / ${fmtBytes(disk.total_bytes)}</div>
      </div>`;
    diskList.appendChild(row);
  }

  const netList = $("net-list");
  netList.innerHTML = "";
  for (const [name, iface] of Object.entries(data.network)) {
    const row = document.createElement("div");
    row.className = "net-row";
    const rate = iface.rate
      ? `↓ ${fmtRate(iface.rate.recv_bytes_per_sec)}  ↑ ${fmtRate(iface.rate.sent_bytes_per_sec)}`
      : "midiendo…";
    row.innerHTML = `
      <div>${name}</div>
      <div style="text-align:right; color:var(--muted)">
        <div>${rate}</div>
        <div style="font-size:0.75rem">total ↓${fmtBytes(iface.bytes_recv)} ↑${fmtBytes(iface.bytes_sent)}</div>
      </div>`;
    netList.appendChild(row);
  }
}

async function authedFetch(path) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) throw new Error(`http ${res.status}`);
  return res.json();
}

async function loadAccessStats() {
  try {
    const stats = await authedFetch("/api/access/stats");
    $("access-today").textContent = stats.today;
    $("access-week").textContent = stats.last_7_days;
    $("access-total").textContent = stats.total;
    $("access-ips").textContent = stats.unique_ips_last_7_days;

    accessChart.data.labels = stats.daily_counts_last_14_days.map((d) =>
      new Date(d.date + "T00:00:00").toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" })
    );
    accessChart.data.datasets[0].data = stats.daily_counts_last_14_days.map((d) => d.hits);
    accessChart.update();

    const tbody = $("access-recent");
    tbody.innerHTML = "";
    for (const row of stats.recent) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${new Date(row.ts).toLocaleTimeString()}</td>
        <td>${row.method}</td>
        <td>${row.path}</td>
        <td>${row.client_ip ?? ""}</td>
        <td>${row.status_code ?? ""}</td>`;
      tbody.appendChild(tr);
    }
  } catch (e) {
    console.error("Error cargando estadísticas de acceso", e);
  }
}

let socket = null;

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/metrics?token=${encodeURIComponent(getToken())}`);

  socket.onopen = () => {
    $("conn-dot").className = "dot dot-on";
    $("conn-text").textContent = "Conectado";
  };

  socket.onmessage = (event) => {
    renderSnapshot(JSON.parse(event.data));
  };

  socket.onclose = (event) => {
    $("conn-dot").className = "dot dot-off";
    $("conn-text").textContent = "Desconectado";
    if (event.code === 4401) {
      showLogin("Token inválido.");
      return;
    }
    setTimeout(connectWebSocket, 5000);
  };

  socket.onerror = () => socket.close();
}

function showLogin(message) {
  $("login").classList.remove("hidden");
  $("dashboard").classList.add("hidden");
  if (message) {
    $("login-error").textContent = message;
    $("login-error").classList.remove("hidden");
  }
}

function showDashboard() {
  $("login").classList.add("hidden");
  $("dashboard").classList.remove("hidden");
}

async function boot() {
  if (!getToken()) {
    showLogin();
    return;
  }
  try {
    await authedFetch("/api/metrics");
    showDashboard();
    connectWebSocket();
    loadAccessStats();
    setInterval(loadAccessStats, 30000);
  } catch (e) {
    showLogin("Token inválido o expirado.");
  }
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setToken($("token-input").value.trim());
  $("login-error").classList.add("hidden");
  await boot();
});

boot();
