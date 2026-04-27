from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <html>
    <head>
        <title>Today Attendance</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 24px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background: #f5f5f5; }
            .present { color: #0a7a31; font-weight: bold; }
            .away { color: #b42318; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Today Attendance</h1>
        <p id="meta">Loading...</p>

        <table>
            <thead>
                <tr>
                    <th>User ID</th>
                    <th>Status</th>
                    <th>Total Seconds</th>
                    <th>Clock In</th>
                    <th>Clock Out Confirmed</th>
                    <th>Detail</th>
                </tr>
            </thead>
            <tbody id="rows"></tbody>
        </table>

        <script>
            let baseItems = [];
            let serverOffset = 0;
            let lastFetchClientMs = Date.now();

            function esc(value) {
                if (value === null || value === undefined) return "-";
                return String(value)
                    .replaceAll("&", "&amp;")
                    .replaceAll("<", "&lt;")
                    .replaceAll(">", "&gt;");
            }

            function formatDate(value) {
                if (!value) return "-";
                const d = new Date(value);
                if (Number.isNaN(d.getTime())) return value;
                return d.toLocaleString();
            }

            async function fetchAttendance() {
                const res = await fetch(`/attendance`);
                const data = await res.json();
                const serverNow = new Date(data.server_time).getTime();
                const clientNow = Date.now();

                serverOffset = serverNow - clientNow;
                lastFetchClientMs = clientNow;
                baseItems = Array.isArray(data.items) ? data.items : [];

                document.getElementById("meta").innerText =
                    `Date: ${data.date || "-"} | Total User: ${data.count || 0}`;

                renderRows();
            }

            function renderRows() {
                const nowClient = Date.now();
                const elapsedSec = Math.max(0, Math.floor((nowClient - lastFetchClientMs) / 1000));

                const html = baseItems.map((item) => {
                    const status = item.status || "AWAY";
                    const isPresent = status === "PRESENT";
                    const totalSeconds = Number(item.total_seconds || 0) + (isPresent ? elapsedSec : 0);
                    const statusClass = isPresent ? "present" : "away";
                    const userId = esc(item.user_id);

                    return `
                        <tr>
                            <td>${userId}</td>
                            <td class="${statusClass}">${esc(status)}</td>
                            <td>${totalSeconds}</td>
                            <td>${esc(formatDate(item.clock_in_at))}</td>
                            <td>${esc(formatDate(item.clock_out_confirmed_at))}</td>
                            <td><a href="/${encodeURIComponent(item.user_id)}">View</a></td>
                        </tr>
                    `;
                }).join("");

                document.getElementById("rows").innerHTML = html || `
                    <tr>
                        <td colspan="6">Belum ada data attendance hari ini</td>
                    </tr>
                `;
            }

            fetchAttendance();
            setInterval(fetchAttendance, 5000);
            setInterval(renderRows, 1000);
        </script>
    </body>
    </html>
    """


@router.get("/{user_id}", response_class=HTMLResponse)
def user_dashboard(user_id: str):
    user_id_json = json.dumps(user_id)
    return f"""
    <html>
    <head>
        <title>Attendance User</title>
    </head>
    <body>
        <h1>Work Countdown</h1>
        <p id="meta"></p>
        <h2 id="timer">Loading...</h2>

        <script>
            const userId = {user_id_json};

            let baseTotal = 0;
            let activeStart = null;
            let serverOffset = 0;
            let isPresent = false;

            function formatTime(sec) {{
                let h = Math.floor(sec / 3600);
                let m = Math.floor((sec % 3600) / 60);
                let s = sec % 60;

                return `${{String(h).padStart(2, '0')}}:${{String(m).padStart(2, '0')}}:${{String(s).padStart(2, '0')}}`;
            }}

            async function fetchInitial() {{
                const res = await fetch(`/attendance/${{userId}}`);
                const data = await res.json();
                applyState(data);
            }}

            function applyState(data) {{
                const serverNow = new Date(data.server_time).getTime();
                const clientNow = Date.now();

                serverOffset = serverNow - clientNow;
                baseTotal = typeof data.total_seconds === "number" ? data.total_seconds : 0;
                activeStart = data.active_start ? new Date(data.active_start).getTime() : null;
                isPresent = data.status === "PRESENT";

                document.getElementById("meta").innerText =
                    `User: ${{userId}} | Status: ${{data.status || "AWAY"}}`;
            }}

            function tick() {{
                const now = Date.now() + serverOffset;
                let total = baseTotal;

                if (activeStart && isPresent) {{
                    total += (now - activeStart) / 1000;
                }}

                let remaining = 28800 - total;
                if (remaining < 0) remaining = 0;

                document.getElementById("timer").innerText =
                    formatTime(Math.floor(remaining));
            }}

            function connectWS() {{
                const ws = new WebSocket(`ws://${{location.host}}/ws`);

                ws.onopen = () => {{
                    console.log("WS connected");
                }};

                ws.onmessage = (event) => {{
                    const data = JSON.parse(event.data);

                    if (data.user_id === userId) {{
                        console.log("Realtime update:", data);
                        applyState(data);
                    }}
                }};

                ws.onclose = () => {{
                    console.log("WS disconnected, reconnecting...");
                    setTimeout(connectWS, 2000);
                }};
            }}

            fetchInitial();
            connectWS();
            setInterval(tick, 1000);
        </script>
    </body>
    </html>
    """