from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <html>
    <head>
        <title>Attendance Dashboard</title>
    </head>
    <body>
        <h1>Work Countdown</h1>
        <p id="meta"></p>
        <h2 id="timer">Loading...</h2>

        <script>
            const params = new URLSearchParams(window.location.search);
            const employeeId = params.get("employee_id") || "EMP001";

            let baseTotal = 0;
            let activeStart = null;
            let serverOffset = 0;
            let isPresent = false;

            function formatTime(sec) {
                let h = Math.floor(sec / 3600);
                let m = Math.floor((sec % 3600) / 60);
                let s = sec % 60;

                return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            }

            // ===== INITIAL LOAD =====
            async function fetchInitial() {
                const res = await fetch(`/attendance/${employeeId}`);
                const data = await res.json();

                applyState(data);
            }

            // ===== APPLY STATE =====
            function applyState(data) {
                const serverNow = new Date(data.server_time).getTime();
                const clientNow = Date.now();

                serverOffset = serverNow - clientNow;

                baseTotal = data.total_seconds;

                activeStart = data.active_start
                    ? new Date(data.active_start).getTime()
                    : null;

                isPresent = data.status === "PRESENT";

                document.getElementById("meta").innerText =
                    `Employee: ${employeeId} | Status: ${data.status}`;
            }

            // ===== REALTIME COUNTDOWN =====
            function tick() {
                const now = Date.now() + serverOffset;

                let total = baseTotal;

                if (activeStart && isPresent) {
                    total += (now - activeStart) / 1000;
                }

                let remaining = 28800 - total;
                if (remaining < 0) remaining = 0;

                document.getElementById("timer").innerText =
                    formatTime(Math.floor(remaining));
            }

            // ===== WEBSOCKET =====
            function connectWS() {
                const ws = new WebSocket(`ws://${location.host}/ws`);

                ws.onopen = () => {
                    console.log("WS connected");
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);

                    if (data.employee_id === employeeId) {
                        console.log("Realtime update:", data);

                        // 🔥 langsung apply state dari backend
                        applyState(data);
                    }
                };

                ws.onclose = () => {
                    console.log("WS disconnected, reconnecting...");
                    setTimeout(connectWS, 2000);
                };
            }

            // ===== INIT =====
            fetchInitial();
            connectWS();

            setInterval(tick, 1000);
        </script>
    </body>
    </html>
    """