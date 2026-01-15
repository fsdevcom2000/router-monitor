const term = new Terminal({
    cursorBlink: true,
    fontFamily: "monospace",
    fontSize: 14,
    theme: {
        background: "#000000",
        foreground: "#ffffff"
    }
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);

term.open(document.getElementById('terminal'));
fitAddon.fit();

// Resize support
window.addEventListener("resize", () => fitAddon.fit());

// WebSocket connection
const ws = new WebSocket(`ws://${location.host}/ws/ssh/${window.ROUTER_NAME}`);

ws.onmessage = e => term.write(e.data);
term.onData(data => ws.send(data));
