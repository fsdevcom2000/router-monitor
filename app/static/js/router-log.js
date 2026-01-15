
const router = window.ROUTER_NAME;
const ws = new WebSocket(`ws://${location.host}/ws/log/${router}`);

const output = document.getElementById("log-output");
const searchBox = document.getElementById("search");
const filters = document.querySelectorAll(".topic-filter");

let allLogs = [];

// --- Highlight helpers ---
function highlightIPs(text) {
    return text.replace(
        /\b\d{1,3}(\.\d{1,3}){3}\b/g,
        '<span class="ip">$&</span>'
    );
}

function highlightMACs(text) {
    return text.replace(
        /\b[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}\b/g,
        '<span class="mac">$&</span>'
    );
}

function makeTag(topic) {
    const cls = {
        system: "tag-system",
        info: "tag-info",
        warning: "tag-warning",
        error: "tag-error",
        account: "tag-account",
        wireless: "tag-wireless",
        dhcp: "tag-dhcp",
        interface: "tag-interface",
        firewall: "tag-firewall",
        script: "tag-script",
    }[topic] || "tag-info";

    return `<span class="tag ${cls}">${topic}</span>`;
}

// --- Format log dict into pretty HTML ---
function formatLog(raw) {
    let obj;
    try { obj = JSON.parse(raw); }
    catch { return raw; }

    const time = obj.time || "";
    const topics = (obj.topics || "").split(",");
    const msg = obj.message || "";
    const extra = obj["extra-info"] || "";

    const tags = topics.map(t => makeTag(t)).join(" ");

    let line = `${time}  ${tags}  ${msg}`;
    line = highlightIPs(line);
    line = highlightMACs(line);

    if (extra) {
        return line + `\n<details><summary>extra-info</summary>${extra}</details>`;
    }

    return line;
}

// --- Render logs with filters + search ---
function renderLogs() {
    const search = searchBox.value.toLowerCase();
    const activeTopics = [...filters].filter(f => f.checked).map(f => f.value);

    output.innerHTML = "";

    for (const log of allLogs) {
        const lower = log.raw.toLowerCase();

        if (search && !lower.includes(search)) continue;
        if (!log.topics.some(t => activeTopics.includes(t))) continue;

        const div = document.createElement("div");
        div.innerHTML = log.html;
        output.appendChild(div);
    }

    output.scrollTop = output.scrollHeight;
}


// --- WebSocket events ---
ws.onmessage = (event) => {
    const raw = event.data;
    console.log("WS RAW:", raw);

    let obj;
    try {
        obj = JSON.parse(raw);
    } catch (e) {
        console.error("JSON parse failed:", raw);
        return;
    }

    const topics = (obj.topics || "").split(",");

    allLogs.push({
        raw,
        topics,
        html: formatLog(raw)
    });

    renderLogs();
};


ws.onclose = () => {
    alert("Log Loaded");
};

// --- Save logs ---
function SaveLog() {
    const output = document.getElementById("log-output");
    if (!output) return;

    const lines = [...output.children]
        .map(el => el.innerText)
        .join("\n");

    if (!lines.trim()) {
        alert("Log is empty");
        return;
    }

    const blob = new Blob([lines], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;

    const now = new Date();
    const timestamp = now.toISOString().replace(/[:]/g, "-");
    // filename: routername_YYYY-MM-DD_HH-MM-SS.txt
    filename = `${router}_${timestamp}.txt`;
    a.download = filename;

    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}


// --- Clear logs ---
function clearLogs() {
    allLogs = [];
    renderLogs();
}

// --- Bind search + filters ---
searchBox.oninput = renderLogs;
filters.forEach(f => f.onchange = renderLogs);
