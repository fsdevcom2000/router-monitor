import { alertModal, confirmModal } from "./modal.js";
import { showToast } from "./toast.js";

const loader = document.getElementById("log-loader");
loader.classList.remove("hidden");

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

// --- Format log object into pretty HTML ---
function formatLog(obj) {
    const time = obj.time || "";
    const topics = Array.isArray(obj.topics) ? obj.topics : [];
    const msg = obj.message || "";
    const raw = obj.raw || "";

    const tags = topics.map(t => makeTag(t)).join(" ");

    let line = `${time}  ${tags}  ${msg}`;
    line = highlightIPs(line);
    line = highlightMACs(line);

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
    let obj;
    try {
        obj = JSON.parse(event.data);
    } catch (e) {
        console.error("JSON parse failed:", event.data);
        loader.classList.add("hidden");
        return;
    }

    // --- Error from backend ---
    if (obj.type === "error") {
        loader.classList.add("hidden");
        alertModal(obj.message || "Unknown error");
        return;
    }

    // --- Logs packet ---
    if (obj.type === "logs" && Array.isArray(obj.logs)) {
        loader.classList.add("hidden"); // Hide spinner when logs arrive

        for (const log of obj.logs) {
            allLogs.push({
                raw: log.raw || "",
                topics: Array.isArray(log.topics) ? log.topics : [],
                html: formatLog(log)
            });
        }
        renderLogs();
        return;
    }

    console.warn("Unknown WS message:", obj);
};

ws.onclose = () => {
    loader.classList.add("hidden");
    showToast("Log load complete", "info");
};

// --- Save logs ---
function SaveLog() {
    const output = document.getElementById("log-output");
    if (!output) return;

    const lines = [...output.children]
        .map(el => el.innerText)
        .join("\n");

    if (!lines.trim()) {
        alertModal("Log is empty");
        return;
    }

    const blob = new Blob([lines], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;

    const now = new Date();
    const timestamp = now.toISOString().replace(/[:]/g, "-");
    const filename = `${router}_${timestamp}.txt`;
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

// --- Make functions available in HTML buttons ---
window.clearLogs = clearLogs;
window.SaveLog = SaveLog;
