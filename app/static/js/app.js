
const routerNames = window.ROUTER_NAMES || [];
const container = document.getElementById("routers-container");
const searchInput = document.getElementById("search");

function showServerAlert() {
  document.getElementById("server-alert").classList.remove("hidden");
}

function hideServerAlert() {
  document.getElementById("server-alert").classList.add("hidden");
}

function createCard(name) {
  const card = document.createElement("div");
  card.className = "card collapsed";
  card.dataset.name = name.toLowerCase();

  card.innerHTML = `
    <div class="card-header">
      <h2>${name}
        <span id="status-${name}" class="status-indicator offline"></span>
      </h2>
      <span class="card-toggle">▼</span>
    </div>

    <div class="card-body">
      ${metric("Device", `board-${name}`)}
      ${metric("Uptime", `uptime-${name}`)}
      ${metric("Firmware", `version-${name}`)}
      ${metric("CPU Temp", `temperature-${name}`)}
      ${metric("CPU Load", `cpu_load-${name}`)}
      ${metric("CPU Freq", `cpu_freq-${name}`)}
      ${metric("Memory", `memory-${name}`)}
      ${metric("Storage", `hdd-${name}`)}
      ${metric("Voltage", `voltage-${name}`)}
      ${metric("WAN", `ipv4-${name}`)}
      ${metric("Interface", `iface-${name}`)}
      ${metric("Rx/Tx (kbps)", `speed-${name}`)}
      ${metric("Reconnects", `reconnects-${name}`)}
    </div>
    <hr class="card-divider">
    <div class="card-actions">
       <button class="card-btn log"
              data-action="log"
              data-router="${name}"
              title="Open router's Log (last 100 lines)">
        log
      </button>

      <button class="card-btn webfig"
              data-action="webfig"
              data-router="${name}"
              title="Webfig">
        webfig
      </button>

      <button class="card-btn terminal"
              data-action="terminal"
              data-router="${name}"
              title="Open terminal">
        >_
      </button>
    </div>
  `;

  container.appendChild(card);
}

function metric(label, id) {
  return `
    <div class="metric">
      <span class="label">${label}:</span>
      <span id="${id}" class="value">--</span>
    </div>
  `;
}

routerNames.forEach(createCard);
container.addEventListener("click", (e) => {
  const btn = e.target.closest(".card-btn");
  if (!btn) return;

  e.stopPropagation(); //

  const action = btn.dataset.action;
  const router = btn.dataset.router;

  if (action === "webfig") {
    openWebfig(router);
    return;
}

  if (action === "terminal") {
    openTerminal(router);
  }
  if (action === "log") {
    openLog(router);
  }

});
/* toggle */
container.addEventListener("click", (e) => {
  const header = e.target.closest(".card-header");
  if (!header || !container.contains(header)) return;

  const card = header.closest(".card");
  if (!card) return;

  card.classList.toggle("collapsed");
});

/* toggle-all/collapse-all */
const toggleAllBtn = document.getElementById("toggle-all");

toggleAllBtn.addEventListener("click", () => {
  const cards = document.querySelectorAll(".card");
  const allCollapsed = [...cards].every(c => c.classList.contains("collapsed"));
  cards.forEach(c => c.classList.toggle("collapsed", !allCollapsed));
  toggleAllBtn.textContent = allCollapsed ? "▸▸" : "▾▾";
});

/* search */
searchInput.addEventListener("input", e => {
  const term = e.target.value.toLowerCase();
  document.querySelectorAll(".card").forEach(card => {
    card.style.display = card.dataset.name.includes(term) ? "" : "none";
  });
});

/* WebSocket status update with token auth and auto-reconnect */
async function connectWS() {
  try {
    // get token from backend
    const r = await fetch("/ws-token");
    if (!r.ok) throw new Error("Failed to get WS token");
    const { token } = await r.json();

    const ws = new WebSocket(`ws://${location.host}/ws/status?token=${token}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      routerNames.forEach(name => {
        const d = data[name] || {};
        const card = document.querySelector(`[data-name="${name.toLowerCase()}"]`);
        if (card) {
            if (d.webfig_host) card.dataset.webfigHost = d.webfig_host;
            if (d.webfig_proto) card.dataset.webfigProto = d.webfig_proto;
            if (d.webfig_port) card.dataset.webfigPort = d.webfig_port;
            if (d.log) card.dataset.log = JSON.stringify(d.log);
        }
        set(`ipv4-${name}`, d.ipv4);
        set(`board-${name}`, d.board);
        set(`uptime-${name}`, d.uptime);
        set(`version-${name}`, d.version);
        set(`iface-${name}`, d.iface);
        set(`speed-${name}`, d.speed);

        const tReconnects = document.getElementById(`reconnects-${name}`);
        if (d.reconnects != null) {
          tReconnects.textContent = `${d.reconnects}`;
          tReconnects.className = "value " +
            (d.reconnects < 10 ? "low" :
             d.reconnects < 20 ? "normal" : "high");
        }

        const tTemp = document.getElementById(`temperature-${name}`);
        if (d.temperature != null) {
          tTemp.textContent = `${d.temperature} °C`;
          tTemp.className = "value " +
            (d.temperature < 40 ? "low" :
             d.temperature < 60 ? "normal" : "high");
        }

        set(`cpu_load-${name}`, d.cpu_load, "%");
        set(`cpu_freq-${name}`, d.cpu_freq, " MHz");
        set(`memory-${name}`, d.free_memory && d.total_memory
          ? `${d.free_memory} / ${d.total_memory} MiB` : "--");
        set(`hdd-${name}`, d.free_hdd && d.total_hdd
          ? `${d.free_hdd} / ${d.total_hdd} MiB` : "--");
        set(`voltage-${name}`, d.voltage, " V");

        const s = document.getElementById(`status-${name}`);
        s.classList.toggle("online", d.status === "Yes");
        s.classList.toggle("offline", d.status !== "Yes");
      });
    };

    ws.onopen = () => {
        hideServerAlert();
    };

    ws.onclose = () => {
      showServerAlert();
      console.log("WebSocket disconnected. Reconnecting in 3s...");
      setTimeout(connectWS, 3000);
    };

    ws.onerror = (e) => {
      console.error("WS error", e);
      ws.close();
    };

  } catch (err) {
    console.error("WS connection failed:", err);
    setTimeout(connectWS, 3000);
  }
}

connectWS();

function set(id, val, suf = "") {
  document.getElementById(id).textContent = val != null ? val + suf : "--";
}

async function openWebfig(router) {
    const card = document.querySelector(`[data-name="${router.toLowerCase()}"]`);
    if (!card) {
        alert("Router's card not found");
        return;
    }

    const host = card.dataset.webfigHost;
    const proto = card.dataset.webfigProto || "http";
    const port = card.dataset.webfigPort || (proto === "https" ? "443" : "80");

    if (!host) {
        alert("WebFig not accessible!");
        return;
    }

    // Create URL
    const makeUrl = (p, prt) => `${p}://${host}:${prt}/webfig/`;

    const primaryUrl = makeUrl(proto, port);
    const fallbackUrl = proto === "https"
        ? makeUrl("http", "80")
        : makeUrl("https", "443");

    // Check URL
    async function check(url) {
        try {
            const r = await fetch(url, { method: "HEAD", mode: "no-cors" });
            return true; // no-cors will not return state, if no error - host alive
        } catch {
            return false;
        }
    }

    // 1. Trying main URL
    if (await check(primaryUrl)) {
        window.open(primaryUrl, "_blank");
        return;
    }

    // 2. Trying fallback
    if (await check(fallbackUrl)) {
        window.open(fallbackUrl, "_blank");
        return;
    }

    alert("No access to Webfig via HTTP and HTTPS");
}


function openTerminal(router) {
    window.open(`/router/${router}/terminal`, "_blank");
}

function openLog(router) {
    const card = document.querySelector(`[data-name="${router.toLowerCase()}"]`);
    if (!card) {
        alert("Router's card not found");
        return;
    }

    const router_log = card.dataset.log;
    // here you can either open a separate page, or a modal, or pass router_log
    window.open(`/router/${router}/log`, "_blank");
}



