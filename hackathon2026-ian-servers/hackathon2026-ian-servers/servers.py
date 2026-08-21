import io
import os
import socket
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request, send_file
import qrcode

app = Flask(__name__)

# ==========================================
# 1. CONFIG & SYSTEM GLOBALS
# ==========================================
ROLE_LEVELS = ["student", "staff", "lecturer", "admin"]
COURSES = ["B BIS DUR campus", "BITW DUR campus", "Bcompt DUR campus"]
SUBJECT_DBS = [
    "OOP152", "SEN152", "IDB152", "ISP152", "TAS152", "FIT152", 
    "WDB152", "IWP152", "EFC152", "DMA152", "DDM162", "STA162"
]
CLASSROOMS = ["AG-ITS", "A1-L1", "B1-L3", "A1-IT4", "AG-IT1", "A1-L2", "B2-L9", "B1-L4", "B1-L1"]
EXCLUDED_ROLES = ["admin", "staff"]

CONNECTED_SCANNERS = []
SCANNER_HEARTBEATS = {}
scanner_lock = threading.Lock()


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


SERVER_URL = f"https://{get_local_ip()}:5000"


def update_classroom_modules():
    now = datetime.now()
    current_day = now.strftime("%A")
    current_time = now.strftime("%H:%M")

    with get_db("users.db") as conn:
        conn.execute("UPDATE scanner_config SET current_module = 'none'")
        active_classes = conn.execute("""
            SELECT classroom, module FROM schedules 
            WHERE day_of_week = ? AND start_time <= ? AND end_time >= ?
        """, (current_day, current_time, current_time)).fetchall()
        
        for classroom, module in active_classes:
            conn.execute("UPDATE scanner_config SET current_module = ? WHERE classroom_name = ?", (module, classroom))


def get_scanner_info(client_id):
    update_classroom_modules()
    with scanner_lock:
        if client_id not in CONNECTED_SCANNERS:
            CONNECTED_SCANNERS.append(client_id)
        idx = CONNECTED_SCANNERS.index(client_id) % len(CLASSROOMS)
        classroom_name = CLASSROOMS[idx]
        SCANNER_HEARTBEATS[classroom_name] = datetime.now()

    with get_db("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT current_module FROM scanner_config WHERE classroom_name = ?", (classroom_name,))
        row = c.fetchone()
        module = row[0] if row else "none"

    return classroom_name, module


def print_terminal_qr(url):
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    print("\n" + "=" * 50)
    print(f" 🔒 HTTPS SCANNER LIVE AT: {url}")
    print(" SCAN QR CODE BELOW WITH YOUR MOBILE PHONE:")
    print("=" * 50)
    qr.print_ascii(invert=True)
    print("=" * 50 + "\n")


# ==========================================
# 2. DATABASE ENGINE
# ==========================================
def get_db(db_name):
    conn = sqlite3.connect(
        f"{db_name}.db" if not db_name.endswith(".db") else db_name, timeout=20.0
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_dbs():
    with get_db("users.db") as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            student_number TEXT PRIMARY KEY,
            name TEXT,
            permission_level TEXT,
            course TEXT
        )""")
        
        conn.execute("""CREATE TABLE IF NOT EXISTS scanner_config (
            classroom_name TEXT PRIMARY KEY,
            current_module TEXT
        )""")
        
        try:
            conn.execute("ALTER TABLE scanner_config ADD COLUMN min_role TEXT DEFAULT 'student'")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE scanner_config ADD COLUMN temp_role TEXT DEFAULT 'none'")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE scanner_config ADD COLUMN temp_unlocked_until TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass

        conn.execute("""CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            day_of_week TEXT,
            start_time TEXT,
            end_time TEXT,
            module TEXT,
            classroom TEXT
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS machine_config (
            machine_id TEXT PRIMARY KEY,
            classroom_name TEXT NOT NULL
        )""")

        default_machines = [
            ("ITS-DBV-PC44", "AG-ITS"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO machine_config (machine_id, classroom_name) VALUES (?,?)",
            default_machines,
        )

        default_scanners = [(room, "none", "student", "none") for room in CLASSROOMS]
        conn.executemany("INSERT OR IGNORE INTO scanner_config (classroom_name, current_module, min_role, temp_role) VALUES (?,?,?,?)", default_scanners)

        records = [
            ("26304875", "abisha", "student", "BITW DUR campus"),
            ("26303667", "Maritz", "student", "Bcompt DUR campus"),
            ("26304792", "Daniel", "admin", "none"),
            ("26303890", "Ben", "lecturer", "none"),
            ("26303176", "Staff", "staff", "none"),
            ("26301001", "Liam Smith", "student", "Bcompt DUR campus"),
            ("26301002", "Emma Johnson", "student", "Bcompt DUR campus"),
            ("26301003", "Noah Williams", "student", "B BIS DUR campus"),
        ]
        conn.executemany("INSERT OR REPLACE INTO users VALUES (?,?,?,?)", records)

    with get_db("logs.db") as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanner_id TEXT,
            student_number TEXT,
            name TEXT,
            permission_level TEXT,
            timestamp DATETIME,
            status TEXT
        )""")

    for sub in SUBJECT_DBS:
        init_subject_db(sub)

    seed_schedules()


def init_subject_db(module_name):
    with get_db(module_name) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number TEXT,
            name TEXT,
            role TEXT,
            timestamp DATETIME,
            status TEXT
        )""")


def seed_schedules():
    schedules = [
        ("B BIS DUR campus", "Monday", "08:50", "09:30", "OOP152", "AG-ITS"),
        ("B BIS DUR campus", "Monday", "09:40", "10:20", "SEN152", "AG-ITS"),
        ("B BIS DUR campus", "Monday", "10:30", "11:10", "IDB152", "AG-ITS"),
        ("B BIS DUR campus", "Monday", "11:20", "12:00", "ISP152", "AG-ITS"),
        ("B BIS DUR campus", "Monday", "12:10", "12:50", "ISP152", "AG-ITS"),
        ("B BIS DUR campus", "Wednesday", "11:20", "12:00", "TAS152", "A1-L1"),
        ("B BIS DUR campus", "Wednesday", "12:10", "12:50", "TAS152", "A1-L1"),
        ("B BIS DUR campus", "Wednesday", "13:50", "14:30", "FIT152", "A1-L1"),
        ("B BIS DUR campus", "Wednesday", "14:40", "15:20", "IDB152", "AG-ITS"),
        ("B BIS DUR campus", "Wednesday", "15:30", "16:10", "IDB152", "AG-ITS"),
        ("B BIS DUR campus", "Thursday", "09:40", "10:20", "OOP152", "AG-ITS"),
        ("B BIS DUR campus", "Thursday", "10:30", "11:10", "OOP152", "AG-ITS"),
        ("B BIS DUR campus", "Thursday", "11:20", "12:00", "OOP152", "AG-ITS"),
        ("B BIS DUR campus", "Thursday", "12:10", "12:50", "ISP152", "AG-ITS"),
        ("B BIS DUR campus", "Friday", "08:00", "08:40", "SEN152", "AG-ITS"),
        ("B BIS DUR campus", "Friday", "08:50", "09:30", "SEN152", "AG-ITS"),
        ("B BIS DUR campus", "Friday", "09:40", "10:20", "FIT152", "B1-L3"),
        ("B BIS DUR campus", "Friday", "10:30", "11:10", "FIT152", "B1-L3"),
        ("B BIS DUR campus", "Friday", "11:20", "12:00", "TAS152", "B1-L3"),
        ("BITW DUR campus", "Monday", "10:30", "11:10", "IDB152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "11:20", "12:00", "ISP152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "12:10", "12:50", "ISP152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "13:00", "13:40", "OOP152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "13:50", "14:30", "WDB152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "14:40", "15:20", "WDB152", "AG-ITS"),
        ("BITW DUR campus", "Monday", "15:30", "16:10", "IWP152", "AG-ITS"),
        ("BITW DUR campus", "Wednesday", "12:10", "12:50", "WDB152", "A1-IT4"),
        ("BITW DUR campus", "Wednesday", "13:00", "13:40", "IWP152", "AG-ITS"),
        ("BITW DUR campus", "Wednesday", "13:50", "14:30", "IWP152", "AG-ITS"),
        ("BITW DUR campus", "Wednesday", "14:40", "15:20", "IDB152", "AG-ITS"),
        ("BITW DUR campus", "Wednesday", "15:30", "16:10", "IDB152", "AG-ITS"),
        ("BITW DUR campus", "Thursday", "12:10", "12:50", "ISP152", "AG-ITS"),
        ("BITW DUR campus", "Thursday", "13:00", "13:40", "OOP152", "AG-ITS"),
        ("BITW DUR campus", "Thursday", "13:50", "14:30", "OOP152", "AG-ITS"),
        ("BITW DUR campus", "Thursday", "14:40", "15:20", "OOP152", "AG-ITS"),
        ("BITW DUR campus", "Friday", "09:40", "10:20", "IWP152", "AG-IT1"),
        ("BITW DUR campus", "Friday", "10:30", "11:10", "IWP152", "AG-IT1"),
        ("BITW DUR campus", "Friday", "13:00", "13:40", "WDB152", "AG-IT1"),
        ("BITW DUR campus", "Friday", "13:50", "14:30", "WDB152", "AG-IT1"),
        ("Bcompt DUR campus", "Monday", "08:00", "08:40", "EFC152", "AG-ITS"),
        ("Bcompt DUR campus", "Monday", "08:50", "09:30", "DMA152", "B1-L3"),
        ("Bcompt DUR campus", "Monday", "11:20", "12:00", "DDM162", "B2-L9"),
        ("Bcompt DUR campus", "Monday", "12:10", "12:50", "DDM162", "B2-L9"),
        ("Bcompt DUR campus", "Monday", "13:00", "13:40", "OOP152", "AG-ITS"),
        ("Bcompt DUR campus", "Monday", "13:50", "14:30", "STA162", "A1-L2"),
        ("Bcompt DUR campus", "Monday", "14:40", "15:20", "STA162", "A1-L2"),
        ("Bcompt DUR campus", "Wednesday", "08:00", "08:40", "DDM162", "A1-L2"),
        ("Bcompt DUR campus", "Wednesday", "08:50", "09:30", "STA162", "B1-L4"),
        ("Bcompt DUR campus", "Wednesday", "10:30", "11:10", "DMA152", "B1-L3"),
        ("Bcompt DUR campus", "Wednesday", "11:20", "12:00", "DMA152", "B1-L3"),
        ("Bcompt DUR campus", "Wednesday", "13:00", "13:40", "EFC152", "A1-IT4"),
        ("Bcompt DUR campus", "Wednesday", "13:50", "14:30", "EFC152", "A1-IT4"),
        ("Bcompt DUR campus", "Thursday", "13:00", "13:40", "OOP152", "AG-ITS"),
        ("Bcompt DUR campus", "Thursday", "13:50", "14:30", "OOP152", "AG-ITS"),
        ("Bcompt DUR campus", "Thursday", "14:40", "15:20", "OOP152", "AG-ITS"),
        ("Bcompt DUR campus", "Friday", "08:00", "08:40", "EFC152", "A1-IT4"),
        ("Bcompt DUR campus", "Friday", "08:50", "09:30", "EFC152", "A1-IT4"),
        ("Bcompt DUR campus", "Friday", "09:40", "10:20", "STA162", "B1-L1"),
        ("Bcompt DUR campus", "Friday", "10:30", "11:10", "DDM162", "B1-L1"),
    ]
    with get_db("users.db") as conn:
        conn.execute("DELETE FROM schedules")
        conn.executemany("""
            INSERT INTO schedules (course, day_of_week, start_time, end_time, module, classroom) 
            VALUES (?,?,?,?,?,?)
        """, schedules)


# ==========================================
# 3. AI CLEANING & ANOMALY ENGINE
# ==========================================
class AttendanceAIEngine:

    @staticmethod
    def clean_and_filter(raw_input):
        if not raw_input:
            return None, "Empty payload"
        cleaned = "".join(filter(str.isdigit, str(raw_input).strip()))
        if len(cleaned) != 8:
            return None, f"Invalid format: '{cleaned}' must be 8 digits"
        return cleaned, None

    @staticmethod
    def detect_anomaly(student_number, role):
        fifteen_sec_ago = datetime.now() - timedelta(seconds=15)
        with get_db("logs.db") as conn:
            c = conn.cursor()
            c.execute(
                "SELECT timestamp FROM logs WHERE student_number = ? AND timestamp > ?",
                (student_number, fifteen_sec_ago),
            )
            recent_scan = c.fetchone()

        if recent_scan:
            return True, "ANOMALY: Rapid duplicate scan within 15 seconds."

        current_hour = datetime.now().hour
        if role == "student" and (current_hour < 6 or current_hour > 22):
            return True, "ANOMALY: Off-hours access attempt."

        return False, "Normal pattern"


def lookup_user(student_number):
    with get_db("users.db") as conn:
        return conn.execute(
            "SELECT name, permission_level FROM users WHERE student_number = ?",
            (student_number,),
        ).fetchone()


def get_module_for_classroom(classroom_name):
    update_classroom_modules()
    with get_db("users.db") as conn:
        row = conn.execute(
            "SELECT current_module FROM scanner_config WHERE classroom_name = ?",
            (classroom_name,),
        ).fetchone()
    return row[0] if row else "none"


def get_classroom_for_machine(machine_id):
    with get_db("users.db") as conn:
        row = conn.execute(
            "SELECT classroom_name FROM machine_config WHERE machine_id = ?",
            (machine_id,),
        ).fetchone()
    return row[0] if row else None


def already_present_today(module, student_number):
    init_subject_db(module)
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db(module) as conn:
        row = conn.execute(
            "SELECT id FROM attendance WHERE student_number = ? AND status = 'PRESENT' AND timestamp LIKE ?",
            (student_number, f"{today}%"),
        ).fetchone()
    return row is not None


def check_role_access(permission_level, min_role, temp_role, temp_unlocked_until, classroom_name):
    role_hierarchy = {"student": 1, "staff": 2, "lecturer": 3, "admin": 4}
    user_lvl = role_hierarchy.get(permission_level.lower(), 1)

    now = datetime.now()
    is_unlocked = False
    if temp_unlocked_until:
        try:
            unlocked_until_dt = datetime.strptime(temp_unlocked_until, "%Y-%m-%d %H:%M:%S")
            if now < unlocked_until_dt:
                is_unlocked = True
        except ValueError:
            pass

    has_temp_gate = temp_role and temp_role.lower() != "none"
    required_role = temp_role if has_temp_gate and not is_unlocked else min_role
    req_lvl = role_hierarchy.get(required_role.lower(), 1)

    if user_lvl < req_lvl:
        return False, f"Access Denied: Requires role '{required_role}' to access.", None

    unlocked_until = None
    if has_temp_gate and not is_unlocked and user_lvl >= role_hierarchy.get(temp_role.lower(), 1):
        unlocked_until = (now + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db("users.db") as conn:
            conn.execute(
                "UPDATE scanner_config SET temp_unlocked_until = ? WHERE classroom_name = ?",
                (unlocked_until, classroom_name),
            )

    return True, None, unlocked_until


def mark_attendance(student_number, scanner_id, classroom_name, source="barcode", role_config=None):
    cleaned_id, err = AttendanceAIEngine.clean_and_filter(student_number)
    if err:
        return None, {"status": "REJECTED", "message": err}

    user = lookup_user(cleaned_id)
    if not user:
        return None, {"status": "REJECTED", "message": "User not registered in database."}

    name, permission_level = user
    module = get_module_for_classroom(classroom_name) if classroom_name else "none"

    if source == "barcode" and role_config:
        allowed, role_err, _ = check_role_access(
            permission_level,
            role_config["min_role"],
            role_config["temp_role"],
            role_config["temp_unlocked_until"],
            classroom_name,
        )
        if not allowed:
            return None, {"status": "REJECTED", "message": role_err}

    if source == "heartbeat" and module != "none" and already_present_today(module, cleaned_id):
        return {
            "status": "OK",
            "name": name,
            "role": permission_level,
            "module": module,
            "classroom": classroom_name,
            "source": source,
            "message": "Already marked present today",
        }, None

    if source == "heartbeat":
        is_anomaly = False
        anomaly_msg = ""
    else:
        is_anomaly, anomaly_msg = AttendanceAIEngine.detect_anomaly(cleaned_id, permission_level)

    status_entry = "ANOMALY" if is_anomaly else "PRESENT"

    log_general_access(scanner_id, cleaned_id, name, permission_level, status_entry)

    if permission_level.lower() not in EXCLUDED_ROLES and not is_anomaly and module != "none":
        log_subject_attendance(module, cleaned_id, name, permission_level, status_entry)

    if is_anomaly:
        return None, {"status": "REJECTED", "message": anomaly_msg}

    return {
        "status": "SUCCESS",
        "name": name,
        "role": permission_level,
        "module": module,
        "classroom": classroom_name,
        "source": source,
    }, None


# ==========================================
# 4. WEB INTERFACES
# ==========================================
SCANNER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Scanner</title>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <style>
        body { font-family: system-ui, sans-serif; text-align: center; background: #f4f6f8; margin: 0; padding: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 420px; margin: auto; }
        .badge { background: #e6f0ff; color: #0066cc; padding: 8px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 10px; }
        .subject-blue { color: #0056b3; font-weight: bold; }
        #reader { width: 100%; margin-top: 15px; border-radius: 6px; overflow: hidden; }
        input, button { width: 100%; padding: 10px; margin-top: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; font-size: 15px; }
        .btn { background: #0066cc; color: white; border: none; font-weight: bold; cursor: pointer; }
        .status { margin-top: 15px; padding: 10px; border-radius: 5px; text-align: left; font-size: 14px; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔒 Attendance Scanner</h2>
        <div id="scannerBadge" class="badge">Connecting Scanner...</div>
        
        <div id="reader"></div>
        <input type="text" id="manualCode" placeholder="Enter Barcode / Student Number">
        <button class="btn" onclick="processBarcode(document.getElementById('manualCode').value)">Submit Scan</button>
        <div id="result"></div>
    </div>

    <script>
        function updateInfo() {
            fetch('/api/scanner_info')
                .then(res => res.json())
                .then(info => {
                    document.getElementById('scannerBadge').innerHTML = 
                        `Classroom: <strong>${info.classroom}</strong> — Module: <span class="subject-blue">${info.module}</span>`;
                });
        }
        updateInfo();

        setInterval(() => {
            fetch('/api/scanner_heartbeat', { method: 'POST' });
        }, 5000);

        function processBarcode(code) {
            if (!code) return;
            fetch('/api/validate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ barcode: code })
            })
            .then(res => res.json())
            .then(data => {
                let resDiv = document.getElementById('result');
                if(data.status === 'SUCCESS') {
                    resDiv.className = 'status success';
                    resDiv.innerHTML = `✅ <strong>Marked Present</strong><br>Name: ${data.name} (${data.role})<br>Module: <span class="subject-blue">${data.module}</span>`;
                } else {
                    resDiv.className = 'status error';
                    resDiv.innerHTML = `❌ <strong>Access Denied</strong><br>${data.message}`;
                }
            });
        }
        function onScanSuccess(decodedText) { processBarcode(decodedText); }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: {width: 250, height: 150} }, false);
        html5QrcodeScanner.render(onScanSuccess);
    </script>
</body>
</html>
"""

LECTURER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lecturer Portal</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 900px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
        .controls { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; }
        select, button { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
        .blue-subject { color: #0056b3; font-weight: bold; }
        .btn-refresh { background: #0066cc; color: white; border: none; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: center; font-size: 14px; }
        th { background: #f0f2f5; font-weight: bold; }
        .toggle-btn { padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; }
        .status-present { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-absent { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .nav-link { margin-left: auto; color: #0066cc; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>🔑 Lecturer Attendance Management</h2>
            <a href="/admin" class="nav-link">⚙️ Admin Control</a>
        </div>
        
        <div class="controls">
            <label style="font-weight: bold;">Select Subject / Module:</label>
            <select id="moduleSelect" class="blue-subject" onchange="loadAttendance()">
                <option value="OOP152">OOP152</option>
                <option value="SEN152">SEN152</option>
                <option value="IDB152">IDB152</option>
                <option value="ISP152">ISP152</option>
                <option value="TAS152">TAS152</option>
                <option value="FIT152">FIT152</option>
                <option value="WDB152">WDB152</option>
                <option value="IWP152">IWP152</option>
                <option value="EFC152">EFC152</option>
                <option value="DMA152">DMA152</option>
                <option value="DDM162">DDM162</option>
                <option value="STA162">STA162</option>
            </select>
            <button class="btn-refresh" onclick="loadAttendance()">🔄 Refresh Table</button>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Date</th>
                    <th>Attendance Status</th>
                </tr>
            </thead>
            <tbody id="attendanceBody"></tbody>
        </table>
    </div>

    <script>
        function loadAttendance() {
            const mod = document.getElementById('moduleSelect').value;
            fetch(`/api/lecturer/attendance?module=${mod}`)
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('attendanceBody');
                tbody.innerHTML = '';
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">No students enrolled in a course with this subject.</td></tr>';
                    return;
                }
                data.forEach(row => {
                    const isPresent = (row.status === 'PRESENT' || row.status === 'GRANTED');
                    const btnClass = isPresent ? 'status-present' : 'status-absent';
                    const icon = isPresent ? '✅ Present' : '❌ Absent';
                    const nextStatus = isPresent ? 'ABSENT' : 'PRESENT';

                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${row.student_number}</strong></td>
                            <td>${row.name}</td>
                            <td>${row.role}</td>
                            <td>${row.date}</td>
                            <td>
                                <button class="toggle-btn ${btnClass}" onclick="toggleAttendance('${row.student_number}', '${row.name}', '${row.role}', '${nextStatus}')">
                                    ${icon}
                                </button>
                            </td>
                        </tr>
                    `;
                });
            });
        }

        function toggleAttendance(studentNumber, name, role, newStatus) {
            const mod = document.getElementById('moduleSelect').value;
            fetch('/api/lecturer/attendance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    module: mod,
                    student_number: studentNumber,
                    name: name,
                    role: role,
                    status: newStatus
                })
            }).then(() => loadAttendance());
        }

        loadAttendance();
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 950px; margin: auto; }
        .card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 25px; }
        h2, h3 { margin-top: 0; color: #111; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: center; font-size: 14px; }
        th { background: #f0f2f5; font-weight: bold; }
        .blue-subject { color: #0056b3; font-weight: bold; }
        input, select, button { padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
        .btn-save { background: #28a745; color: white; border: none; font-weight: bold; cursor: pointer; }
        .btn-save:hover { background: #218838; }
        .nav-links { display: flex; gap: 15px; margin-bottom: 15px; }
        .nav-links a { color: #0066cc; text-decoration: none; font-weight: bold; }
        .badge-active { background: #d4edda; color: #155724; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
        .badge-offline { background: #f8d7da; color: #721c24; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
        .badge-temp { background: #fff3cd; color: #856404; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
        .toast { display: none; background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="/">📱 Mobile Scanner Page</a>
            <a href="/lecturer">🔑 Lecturer Portal</a>
        </div>

        <div id="toast" class="toast">Changes Saved Successfully!</div>

        <div class="card">
            <h3>📅 Student Timetable & Attendance Inspector</h3>
            <p style="font-size: 13px; color: #666;">Select a student to view their registered course timetable, classroom locations, scheduled dates, and attendance status:</p>
            <div style="margin-bottom: 15px;">
                <label style="font-weight: bold;">Select Student: </label>
                <select id="studentSelect" onchange="loadStudentSchedule()"></select>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Day</th>
                        <th>Time</th>
                        <th class="blue-subject">Module</th>
                        <th>Classroom</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="studentScheduleTable"></tbody>
            </table>
        </div>

        <div class="card">
            <h3>⚙️ Classroom Scanners & Configuration</h3>
            <p style="font-size: 13px; color: #666;">View real-time active classroom scanners, assigned modules, minimum, and temporary access levels:</p>
            <table>
                <thead>
                    <tr>
                        <th>Classroom Scanner</th>
                        <th>Status</th>
                        <th class="blue-subject">Active Module</th>
                        <th>Min Access Level</th>
                        <th>Temp Access Level</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="scannerTable"></tbody>
            </table>
        </div>

        <div class="card">
            <h3>👥 User Permissions & Course Enrollment</h3>
            <p style="font-size: 13px; color: #666;">Edit roles and enrolled course timetables for registered users:</p>
            <table>
                <thead>
                    <tr>
                        <th>Student Number</th>
                        <th>Full Name</th>
                        <th>Course Timetable</th>
                        <th>Permission Level</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="usersTable"></tbody>
            </table>
        </div>
    </div>

    <script>
        const ALL_MODULES = ["none", "OOP152", "SEN152", "IDB152", "ISP152", "TAS152", "FIT152", "WDB152", "IWP152", "EFC152", "DMA152", "DDM162", "STA162"];
        const ALL_ROLES = ["student", "staff", "lecturer", "admin"];
        const TEMP_ROLES = ["none", "student", "staff", "lecturer", "admin"];

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        function loadStudentDropdown() {
            fetch('/api/admin/users')
            .then(res => res.json())
            .then(data => {
                const sel = document.getElementById('studentSelect');
                sel.innerHTML = '';
                data.forEach(u => {
                    if (u.permission_level === 'student') {
                        sel.innerHTML += `<option value="${u.student_number}">${u.name} (${u.student_number}) - ${u.course}</option>`;
                    }
                });
                loadStudentSchedule();
            });
        }

        function loadStudentSchedule() {
            const studentId = document.getElementById('studentSelect').value;
            if(!studentId) return;
            fetch(`/api/admin/student_schedule?student_id=${studentId}`)
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('studentScheduleTable');
                tbody.innerHTML = '';
                if(data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6">No schedule found for this student.</td></tr>';
                    return;
                }
                data.forEach(row => {
                    const badge = row.status === 'Present' 
                        ? `<span class="badge-active">✅ Present</span>` 
                        : `<span class="badge-offline">❌ Absent</span>`;
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${row.date}</strong></td>
                            <td>${row.day}</td>
                            <td>${row.time}</td>
                            <td class="blue-subject">${row.module}</td>
                            <td>${row.classroom}</td>
                            <td>${badge}</td>
                        </tr>
                    `;
                });
            });
        }

        function loadScanners() {
            fetch('/api/admin/scanners')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('scannerTable');
                tbody.innerHTML = '';
                data.forEach(s => {
                    let statusBadge = s.active 
                        ? `<span class="badge-active">🟢 Active</span>` 
                        : `<span class="badge-offline">⚪ Offline</span>`;
                    
                    if (s.temp_unlocked) {
                        statusBadge += `<br><span class="badge-temp">🔓 Unlocked (30m)</span>`;
                    }

                    let moduleOptions = ALL_MODULES.map(m => 
                        `<option value="${m}" ${s.current_module === m ? 'selected' : ''}>${m}</option>`
                    ).join('');

                    let roleOptions = ALL_ROLES.map(r => 
                        `<option value="${r}" ${s.min_role === r ? 'selected' : ''}>${r}</option>`
                    ).join('');

                    let tempRoleOptions = TEMP_ROLES.map(r => 
                        `<option value="${r}" ${s.temp_role === r ? 'selected' : ''}>${r}</option>`
                    ).join('');
                        
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${s.classroom_name} Scanner</strong></td>
                            <td>${statusBadge}</td>
                            <td>
                                <select class="blue-subject" id="scanner-mod-${s.classroom_name}">
                                    ${moduleOptions}
                                </select>
                            </td>
                            <td>
                                <select id="scanner-role-${s.classroom_name}">
                                    ${roleOptions}
                                </select>
                            </td>
                            <td>
                                <select id="scanner-temprole-${s.classroom_name}">
                                    ${tempRoleOptions}
                                </select>
                            </td>
                            <td><button class="btn-save" onclick="updateScanner('${s.classroom_name}')">Save</button></td>
                        </tr>
                    `;
                });
            });
        }

        function updateScanner(classroom) {
            const newMod = document.getElementById(`scanner-mod-${classroom}`).value;
            const newRole = document.getElementById(`scanner-role-${classroom}`).value;
            const newTempRole = document.getElementById(`scanner-temprole-${classroom}`).value;
            fetch('/api/admin/scanners', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    classroom_name: classroom, 
                    current_module: newMod, 
                    min_role: newRole,
                    temp_role: newTempRole
                })
            })
            .then(res => res.json())
            .then(data => {
                showToast(`Updated Scanner ${classroom}`);
                loadScanners();
            });
        }

        function loadUsers() {
            fetch('/api/admin/users')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('usersTable');
                tbody.innerHTML = '';
                data.forEach(u => {
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${u.student_number}</strong></td>
                            <td>${u.name}</td>
                            <td>
                                <select id="course-${u.student_number}">
                                    <option value="B BIS DUR campus" ${u.course === 'B BIS DUR campus' ? 'selected' : ''}>B BIS DUR campus</option>
                                    <option value="BITW DUR campus" ${u.course === 'BITW DUR campus' ? 'selected' : ''}>BITW DUR campus</option>
                                    <option value="Bcompt DUR campus" ${u.course === 'Bcompt DUR campus' ? 'selected' : ''}>Bcompt DUR campus</option>
                                    <option value="none" ${u.course === 'none' ? 'selected' : ''}>None</option>
                                </select>
                            </td>
                            <td>
                                <select id="role-${u.student_number}">
                                    <option value="student" ${u.permission_level === 'student' ? 'selected' : ''}>Student</option>
                                    <option value="staff" ${u.permission_level === 'staff' ? 'selected' : ''}>Staff</option>
                                    <option value="lecturer" ${u.permission_level === 'lecturer' ? 'selected' : ''}>Lecturer</option>
                                    <option value="admin" ${u.permission_level === 'admin' ? 'selected' : ''}>Admin</option>
                                </select>
                            </td>
                            <td><button class="btn-save" onclick="updateUser('${u.student_number}')">Save</button></td>
                        </tr>
                    `;
                });
            });
        }

        function updateUser(studentNumber) {
            const newRole = document.getElementById(`role-${studentNumber}`).value;
            const newCourse = document.getElementById(`course-${studentNumber}`).value;
            fetch('/api/admin/users', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_number: studentNumber, permission_level: newRole, course: newCourse })
            })
            .then(res => res.json())
            .then(data => {
                showToast(`Updated profile for ${studentNumber}`);
                loadUsers();
                loadStudentDropdown();
            });
        }

        loadStudentDropdown();
        loadScanners();
        loadUsers();
        setInterval(loadScanners, 5000);
    </script>
</body>
</html>
"""


# ==========================================
# 5. API & ROUTES
# ==========================================
@app.route("/")
def index():
    return render_template_string(SCANNER_HTML)


@app.route("/lecturer")
def lecturer_portal():
    return render_template_string(LECTURER_HTML)


@app.route("/admin")
def admin_portal():
    return render_template_string(ADMIN_HTML)


@app.route("/qr")
def get_qr():
    img = qrcode.make(SERVER_URL)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/scanner_heartbeat", methods=["POST"])
def scanner_heartbeat():
    client_id = f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    classroom_name, _ = get_scanner_info(client_id)
    SCANNER_HEARTBEATS[classroom_name] = datetime.now()
    return jsonify({"status": "OK"})


@app.route("/api/scanner_info", methods=["GET"])
def scanner_info():
    client_id = f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    classroom_name, module = get_scanner_info(client_id)
    return jsonify({"classroom": classroom_name, "module": module})


@app.route("/api/validate", methods=["POST"])
def validate():
    data = request.json or {}
    raw_number = data.get("barcode", "")

    client_id = f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    classroom_name, _ = get_scanner_info(client_id)

    with get_db("users.db") as conn:
        sc_config = conn.execute(
            "SELECT min_role, temp_role, temp_unlocked_until FROM scanner_config WHERE classroom_name = ?",
            (classroom_name,),
        ).fetchone()

    role_config = None
    if sc_config:
        role_config = {
            "min_role": sc_config[0] or "student",
            "temp_role": sc_config[1] or "none",
            "temp_unlocked_until": sc_config[2],
        }

    result, error = mark_attendance(
        raw_number,
        f"Classroom Scanner ({classroom_name})",
        classroom_name,
        source="barcode",
        role_config=role_config,
    )

    if error:
        return jsonify(error)
    return jsonify(result)


@app.route("/api/heartbeat", methods=["POST"])
def pc_heartbeat():
    data = request.json or {}
    student_id = data.get("student_id", "")
    machine_id = data.get("machine_id", "")

    if not student_id or not machine_id:
        return jsonify({"status": "REJECTED", "message": "student_id and machine_id are required"}), 400

    classroom_name = get_classroom_for_machine(machine_id)
    if not classroom_name:
        return jsonify({"status": "REJECTED", "message": f"Unknown machine: {machine_id}"}), 404

    result, error = mark_attendance(
        student_id,
        f"PC Login ({machine_id})",
        classroom_name,
        source="heartbeat",
    )

    if error:
        return jsonify(error)
    return jsonify(result)


@app.route("/api/facial_confirm", methods=["POST"])
def facial_confirm():
    data = request.json or {}
    student_ids = data.get("student_ids") or []
    classroom_name = data.get("classroom", "")

    if isinstance(data.get("student_id"), str):
        student_ids = [data["student_id"]]

    if not student_ids:
        return jsonify({"status": "REJECTED", "message": "student_ids is required"}), 400

    if not classroom_name:
        return jsonify({"status": "REJECTED", "message": "classroom is required"}), 400

    if classroom_name not in CLASSROOMS:
        return jsonify({"status": "REJECTED", "message": f"Unknown classroom: {classroom_name}"}), 400

    confirmed = []
    rejected = []

    for student_id in student_ids:
        if student_id == "UNKNOWN":
            rejected.append({"student_id": student_id, "message": "Unrecognized face"})
            continue

        result, error = mark_attendance(
            student_id,
            f"Facial Recognition ({classroom_name})",
            classroom_name,
            source="facial",
        )

        if error:
            rejected.append({"student_id": student_id, "message": error.get("message", "Rejected")})
        else:
            confirmed.append(result)

    return jsonify({
        "status": "SUCCESS" if confirmed else "REJECTED",
        "confirmed": confirmed,
        "rejected": rejected,
        "classroom": classroom_name,
    })


@app.route("/api/admin/scanners", methods=["GET", "POST"])
def handle_admin_scanners():
    if request.method == "GET":
        update_classroom_modules()
        with get_db("users.db") as conn:
            conn.row_factory = sqlite3.Row
            scanners = conn.execute(
                "SELECT classroom_name, current_module, min_role, temp_role, temp_unlocked_until FROM scanner_config ORDER BY classroom_name ASC"
            ).fetchall()

        now = datetime.now()
        scanner_list = []
        for s in scanners:
            s_dict = dict(s)
            c_name = s_dict["classroom_name"]
            last_seen = SCANNER_HEARTBEATS.get(c_name)
            s_dict["active"] = (
                last_seen is not None and (now - last_seen).total_seconds() < 12
            )

            unlocked_until = s_dict.get("temp_unlocked_until")
            s_dict["temp_unlocked"] = False
            if unlocked_until:
                try:
                    s_dict["temp_unlocked"] = now < datetime.strptime(unlocked_until, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            scanner_list.append(s_dict)

        return jsonify(scanner_list)

    elif request.method == "POST":
        data = request.json or {}
        classroom = data.get("classroom_name")
        module = data.get("current_module")
        min_role = data.get("min_role", "student")
        temp_role = data.get("temp_role", "none")

        with get_db("users.db") as conn:
            conn.execute(
                "UPDATE scanner_config SET current_module = ?, min_role = ?, temp_role = ? WHERE classroom_name = ?",
                (module, min_role, temp_role, classroom),
            )

        if module != "none":
            init_subject_db(module)
        return jsonify({"status": "SUCCESS"})


@app.route("/api/admin/users", methods=["GET", "POST"])
def handle_admin_users():
    if request.method == "GET":
        with get_db("users.db") as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute(
                "SELECT student_number, name, permission_level, course FROM users ORDER BY student_number ASC"
            ).fetchall()
        return jsonify([dict(u) for u in users])

    elif request.method == "POST":
        data = request.json or {}
        student_number = data.get("student_number")
        permission_level = data.get("permission_level")
        course = data.get("course")

        with get_db("users.db") as conn:
            conn.execute(
                "UPDATE users SET permission_level = ?, course = ? WHERE student_number = ?",
                (permission_level, course, student_number),
            )
        return jsonify({"status": "SUCCESS"})


@app.route("/api/admin/student_schedule", methods=["GET"])
def get_student_schedule():
    student_id = request.args.get("student_id")
    
    with get_db("users.db") as conn:
        user = conn.execute("SELECT course FROM users WHERE student_number = ?", (student_id,)).fetchone()
        if not user or not user[0]: 
            return jsonify([])
        
        schedules = conn.execute(
            "SELECT day_of_week, start_time, end_time, module, classroom FROM schedules WHERE course = ? ORDER BY id ASC", 
            (user[0],)
        ).fetchall()
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    day_offsets = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}

    result = []
    for sched in schedules:
        day, start_time, end_time, module, classroom = sched
        
        target_date = start_of_week + timedelta(days=day_offsets.get(day, 0))
        date_str = target_date.strftime("%Y-%m-%d")

        status = "Absent"
        try:
            with get_db(module) as mod_conn:
                present = mod_conn.execute(
                    "SELECT timestamp FROM attendance WHERE student_number = ? AND status != 'ANOMALY' ORDER BY id DESC LIMIT 1", 
                    (student_id,)
                ).fetchone()
                if present: 
                    status = "Present"
                    if present[0]:
                        date_str = present[0].split(" ")[0]
        except Exception:
            pass

        result.append({
            "date": date_str,
            "day": day,
            "time": f"{start_time} - {end_time}",
            "module": module,
            "classroom": classroom,
            "status": status
        })
        
    return jsonify(result)


def log_general_access(scanner_id, student_number, name, role, status):
    with get_db("logs.db") as conn:
        conn.execute(
            "INSERT INTO logs (scanner_id, student_number, name, permission_level, timestamp, status) VALUES (?,?,?,?,?,?)",
            (
                scanner_id,
                student_number,
                name,
                role,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status,
            ),
        )


def log_subject_attendance(module, student_number, name, role, status):
    init_subject_db(module)
    with get_db(module) as conn:
        conn.execute(
            "INSERT INTO attendance (student_number, name, role, timestamp, status) VALUES (?,?,?,?,?)",
            (
                student_number,
                name,
                role,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status,
            ),
        )


@app.route("/api/lecturer/attendance", methods=["GET", "POST"])
def handle_lecturer_attendance():
    module = request.args.get("module") or (request.json or {}).get("module")

    if request.method == "GET":
        with get_db("users.db") as conn:
            conn.row_factory = sqlite3.Row
            if module and module != "none":
                enrolled_courses = [
                    r[0] for r in conn.execute(
                        "SELECT DISTINCT course FROM schedules WHERE module = ?", (module,)
                    ).fetchall()
                ]
                if enrolled_courses:
                    placeholders = ",".join(["?"] * len(enrolled_courses))
                    users = conn.execute(
                        f"SELECT student_number, name, permission_level FROM users WHERE course IN ({placeholders}) AND LOWER(permission_level) NOT IN ('admin', 'staff')",
                        enrolled_courses
                    ).fetchall()
                else:
                    users = []
            else:
                users = conn.execute(
                    "SELECT student_number, name, permission_level FROM users WHERE LOWER(permission_level) NOT IN ('admin', 'staff')"
                ).fetchall()

        attendance_map = {}
        if module and module != "none":
            init_subject_db(module)
            with get_db(module) as conn:
                conn.row_factory = sqlite3.Row
                attendance_records = conn.execute(
                    "SELECT student_number, timestamp, status FROM attendance WHERE status != 'ANOMALY' ORDER BY id DESC"
                ).fetchall()

            for row in attendance_records:
                s_num = row["student_number"]
                if s_num not in attendance_map:
                    raw_time = row["timestamp"] or ""
                    date_only = (
                        raw_time.split(" ")[0]
                        if " " in raw_time
                        else datetime.now().strftime("%Y-%m-%d")
                    )
                    attendance_map[s_num] = {
                        "date": date_only,
                        "status": row["status"],
                    }

        today = datetime.now().strftime("%Y-%m-%d")
        response_data = []
        for u in users:
            s_num = u["student_number"]
            record = attendance_map.get(
                s_num, {"date": today, "status": "ABSENT"}
            )
            response_data.append(
                {
                    "student_number": s_num,
                    "name": u["name"],
                    "role": u["permission_level"],
                    "date": record["date"],
                    "status": record["status"],
                }
            )

        return jsonify(response_data)

    elif request.method == "POST":
        data = request.json or {}
        s_num = data.get("student_number")
        name = data.get("name")
        role = data.get("role")
        status = data.get("status", "PRESENT")

        if module and module != "none":
            init_subject_db(module)
            with get_db(module) as conn:
                conn.execute(
                    "INSERT INTO attendance (student_number, name, role, timestamp, status) VALUES (?,?,?,?,?)",
                    (
                        s_num,
                        name,
                        role,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        status,
                    ),
                )
        return jsonify({"status": "SUCCESS"})


# ==========================================
# 6. MAIN HTTPS RUNNER
# ==========================================
if __name__ == "__main__":
    init_dbs()

    print_terminal_qr(SERVER_URL)

    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        ssl_ctx = ("cert.pem", "key.pem")
        print("🔒 Using custom SSL certificates (cert.pem, key.pem).")
    else:
        print("⚠️ Warning: cert.pem/key.pem not found. Falling back to adhoc SSL.")
        ssl_ctx = "adhoc"

    print(f"🔑 Lecturer Portal: {SERVER_URL}/lecturer")
    print(f"⚙️ Admin Control Portal: {SERVER_URL}/admin")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        ssl_context=ssl_ctx,
    )