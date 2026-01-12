
const logBox = document.getElementById("log");
const clearBtn = document.getElementById("clearLog");

// Автоматический выбор ws/wss
const protocol = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${protocol}://${location.host}/ws/logs`);

ws.onopen = () => {
    console.log("Connected to log stream");
};

ws.onmessage = (event) => {
    const line = document.createElement("div");
    line.textContent = event.data;
    logBox.appendChild(line);

    // Autoscroll
    logBox.scrollTop = logBox.scrollHeight;
};

ws.onerror = (err) => {
    console.error("WebSocket error:", err);
};

ws.onclose = () => {
    const line = document.createElement("div");
    line.textContent = "[Disconnected from server]";
    line.style.color = "red";
    logBox.appendChild(line);
};

clearBtn.onclick = () => {
    logBox.innerHTML = "";
};

