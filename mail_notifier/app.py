import os
import time
import threading
import urllib.request
import urllib.error
import ssl
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# === Конфигурация ===
MAIL_SERVER = os.getenv('MAIL_SERVER', 'mail')
MAIL_PORT = int(os.getenv('MAIL_PORT', 25))
ALERT_TO = os.getenv('ALERT_TO', 'user@example.local')
ALERT_FROM = 'monitor@lab.local'
CHECK_URL = os.getenv('CHECK_URL', 'http://web_server:80')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '10'))

# === Хранилище состояния (thread-safe) ===
state_lock = threading.Lock()
monitor_state = {
    'status': 'INIT',
    'last_check': None,
    'response_time_ms': None,
    'history': []
}

def send_alert(subject: str, body: str) -> bool:
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = Header(f'Incident Monitor <{ALERT_FROM}>', 'utf-8')
        msg['To'] = Header(ALERT_TO, 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as s:
            s.sendmail(ALERT_FROM, [ALERT_TO], msg.as_string())
        return True
    except Exception as e:
        with state_lock:
            monitor_state['history'].insert(0, {
                'time': time.strftime('%H:%M:%S'),
                'status': 'MAIL_ERROR',
                'message': str(e)
            })
        return False

def monitor_loop():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    last_alert_time = 0

    while True:
        try:
            start = time.time()
            req = urllib.request.Request(CHECK_URL, headers={'User-Agent': 'Monitor/1.0'})
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            ms = round((time.time() - start) * 1000)
            status = 'UP' if 200 <= resp.status < 300 else f'DOWN ({resp.status})'
            error_msg = 'OK'
        except Exception as e:
            ms = None
            status = f'DOWN ({type(e).__name__})'
            error_msg = str(e)

        with state_lock:
            now = time.strftime('%H:%M:%S')
            monitor_state['status'] = status.split()[0]
            monitor_state['last_check'] = now
            monitor_state['response_time_ms'] = ms
            monitor_state['history'].insert(0, {
                'time': now, 'status': status, 'message': error_msg
            })
            monitor_state['history'] = monitor_state['history'][:50]

            if monitor_state['status'] == 'DOWN' and (time.time() - last_alert_time) > 30:
                send_alert(f"INCIDENT: Web Server {status}", 
                           f"Time: {now}\nURL: {CHECK_URL}\nStatus: {status}\nDetails: {error_msg}")
                last_alert_time = time.time()

        time.sleep(CHECK_INTERVAL)

# === Встроенный HTML-шаблон ===
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Service Monitor</title>
<style>
:root { --bg: #f4f6f8; --card: #ffffff; --border: #e2e8f0; --text: #1e293b; --muted: #64748b; --up: #16a34a; --down: #dc2626; --warn: #ca8a04; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; padding: 2rem; }
.container { max-width: 900px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin-bottom: 1.5rem; font-weight: 600; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }
.card h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.5rem; }
.card .value { font-size: 1.75rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.status-up { color: var(--up); }
.status-down { color: var(--down); }
.status-init { color: var(--muted); }
table { width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
th { background: #f8fafc; font-weight: 500; color: var(--muted); }
tr:last-child td { border-bottom: none; }
.badge { display: inline-block; padding: 0.2em 0.6em; border-radius: 4px; font-size: 0.8rem; font-weight: 500; }
.badge-up { background: #dcfce7; color: var(--up); }
.badge-down { background: #fee2e2; color: var(--down); }
.btn { background: var(--text); color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:hover { opacity: 0.9; }
.actions { margin-top: 1.5rem; }
@media (max-width: 600px) { body { padding: 1rem; } .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">
  <h1>Service Monitor Dashboard</h1>
  <div class="grid">
    <div class="card"><h2>Current Status</h2><div id="status" class="value status-init">Initializing...</div></div>
    <div class="card"><h2>Last Check</h2><div id="last-check" class="value">--:--:--</div></div>
    <div class="card"><h2>Response Time</h2><div id="latency" class="value">-- ms</div></div>
  </div>

  <div class="card">
    <h2>Incident Log</h2>
    <table>
      <thead><tr><th style="width:80px">Time</th><th style="width:100px">Status</th><th>Message</th></tr></thead>
      <tbody id="log-body"><tr><td colspan="3" style="color:var(--muted);text-align:center">Waiting for data...</td></tr></tbody>
    </table>
  </div>

  <div class="actions">
    <button class="btn" onclick="sendTest()">Send Manual Test Alert</button>
  </div>
</div>

<script>
async function update() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    
    const sEl = document.getElementById('status');
    sEl.textContent = data.status;
    sEl.className = 'value status-' + (data.status === 'UP' ? 'up' : data.status === 'DOWN' ? 'down' : 'init');
    
    document.getElementById('last-check').textContent = data.last_check || '--:--:--';
    document.getElementById('latency').textContent = data.response_time_ms ? data.response_time_ms + ' ms' : 'timeout';
    
    const tbody = document.getElementById('log-body');
    tbody.innerHTML = data.history.map(h => `
      <tr>
        <td>${h.time}</td>
        <td><span class="badge ${h.status.includes('DOWN') ? 'badge-down' : 'badge-up'}">${h.status.split('(')[0]}</span></td>
        <td>${h.message}</td>
      </tr>
    `).join('');
  } catch(e) { console.error('Update failed', e); }
}

async function sendTest() {
  const btn = document.querySelector('.btn');
  btn.disabled = true; btn.textContent = 'Sending...';
  await fetch('/api/test', { method: 'POST' });
  btn.disabled = false; btn.textContent = 'Send Manual Test Alert';
  setTimeout(update, 500);
}

update();
setInterval(update, 3000);
</script>
</body>
</html>"""

# === Маршруты ===
@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    with state_lock:
        return jsonify(monitor_state)

@app.route('/api/test', methods=['POST'])
def api_test():
    send_alert("MANUAL TEST ALERT", "Triggered from dashboard at " + time.strftime('%H:%M:%S'))
    return jsonify({"success": True})

if __name__ == '__main__':
    thread = threading.Thread(target=monitor_loop, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)