
    qr.print_ascii(invert=True)
    print("=" * 60 + "\n")


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
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
            student_number TEXT PRIMARY KEY,
            name TEXT,
            permission_level TEXT
        )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scanner_config (
            scanner_id INTEGER PRIMARY KEY,
            module TEXT
        )"""
        )

        default_scanners = [(1, "OOP-152"), (2, "DDM-152"), (3, "DMA-152")]
        conn.executemany(
            "INSERT OR IGNORE INTO scanner_config VALUES (?,?)", default_scanners
        )

        records = [
            ("26303667", "Maritz", "student"),
            ("26304792", "Daniel", "admin"),
            ("26303890", "Ben", "lecturer"),
            ("26303176", "Hendrik", "staff"),
            ("26301001", "Liam Smith", "student"),
            ("26301002", "Emma Johnson", "student"),
            ("26301003", "Noah Williams", "student"),
            ("26301004", "Olivia Brown", "student"),
            ("26301005", "Ethan Jones", "student"),
            ("26301006", "Sophia Garcia", "student"),
            ("26301007", "Mason Miller", "student"),
            ("26301008", "Isabella Davis", "student"),
            ("26301009", "James Rodriguez", "student"),
            ("26301010", "Mia Martinez", "student"),
            ("26301011", "Benjamin Hernandez", "student"),
            ("26301012", "Charlotte Lopez", "student"),
            ("26301013", "Lucas Gonzalez", "student"),
            ("26301014", "Amelia Wilson", "student"),
            ("26301015", "Alexander Anderson", "student"),
        ]
        conn.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?)", records)

    with get_db("logs.db") as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanner_id TEXT,
            student_number TEXT,
            name TEXT,
            permission_level TEXT,
            timestamp DATETIME,
            status TEXT
        )"""
        )

    for sub in SUBJECT_DBS:
        init_subject_db(sub)


def init_subject_db(module_name):
    with get_db(module_name) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number TEXT,
            name TEXT,
            role TEXT,
            timestamp DATETIME,
            status TEXT
        )"""
        )


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
        #reader { width: 100%; margin-top: 15px; border-radius: 6px; overflow: hidden; }
        input, button { width: 100%; padding: 10px; margin-top: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; font-size: 15px; } Attendance Management</h2>
            <a href="/admin" class="nav-link">⚙️ Admin Control</a>
        </div>
        
        <div class="controls">
            <label style="font-weight: bold;">Select Class / Module:</label>
            <select id="moduleSelect" onchange="loadAttendance()">
                <option value="OOP-152">OOP-152 (Scanner 1)</option>
                <option value="DDM-152">DDM-152 (Scanner 2)</option>
                <option value="DMA-152">DMA-152 (Scanner 3)</option>
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
        input, select, button { padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
        .btn-save { background: #28a745; color: white; border: none; font-weight: bold; cursor: pointer; }
        .btn-save:hover { background: #218838; }
        .nav-links { display: flex; gap: 15px; margin-bottom: 15px; }
        .nav-links a { color: #0066cc; text-decoration: none; font-weight: bold; }
        .badge-active { background: #d4edda; color: #155724; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
        .badge-offline { background: #e2e3e5; color: #383d41; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
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
            <h3>⚙️ Scanner Status & Class Mappings</h3>
            <p style="font-size: 13px; color: #666;">View real-time active scanners and configure assigned subject modules:</p>
            <table>
                <thead>
                    <tr>
                        <th>Scanner ID</th>
                        <th>Status</th>
                        <th>Assigned Subject / Class</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="scannerTable"></tbody>
            </table>
        </div>

        <div class="card">
            <h3>👥 User Permissions Management</h3>
            <p style="font-size: 13px; color: #666;">Edit permission levels and roles for registered users:</p>
            <table>
                <thead>
                    <tr>
                        <th>Student / ID Number</th>
                        <th>Full Name</th>
                        <th>Permission Level</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="usersTable"></tbody>
            </table>
        </div>
    </div>

    <script>
        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        function loadScanners() {
            fetch('/api/admin/scanners')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('scannerTable');
                tbody.innerHTML = '';
                data.forEach(s => {
                    const statusBadge = s.active 
                        ? `<span class="badge-active">🟢 Active</span>` 
                        : `<span class="badge-offline">⚪ Offline</span>`;
                        
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>Scanner #${s.scanner_id}</strong></td>
                            <td>${statusBadge}</td>
                            <td>
                                <input type="text" id="scanner-${s.scanner_id}" value="${s.module}">
                            </td>
                            <td>
                                <button class="btn-save" onclick="updateScanner(${s.scanner_id})">Save Mapping</button>
                            </td>
                        </tr>
                    `;
                });
            });
        }

        function updateScanner(id) {
            const newMod = document.getElementById(`scanner-${id}`).value;
            fetch('/api/admin/scanners', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ scanner_id: id, module: newMod })
            })
            .then(res => res.json())
            .then(data => {
                showToast(`Scanner #${id} assigned to ${newMod}`);
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
                                <select id="role-${u.student_number}">
                                    <option value="student" ${u.permission_level === 'student' ? 'selected' : ''}>Student</option>
                                    <option value="staff" ${u.permission_level === 'staff' ? 'selected' : ''}>Staff</option>
                                    <option value="lecturer" ${u.permission_level === 'lecturer' ? 'selected' : ''}>Lecturer</option>
                                    <option value="admin" ${u.permission_level === 'admin' ? 'selected' : ''}>Admin</option>
                                </select>
                            </td>
                            <td>
                                <button class="btn-save" onclick="updateUserRole('${u.student_number}')">Save Role</button>
                            </td>
                        </tr>
                    `;
                });
            });
        }

        function updateUserRole(studentNumber) {
            const newRole = document.getElementById(`role-${studentNumber}`).value;
            fetch('/api/admin/users', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_number: studentNumber, permission_level: newRole })
            })
            .then(res => res.json())
            .then(data => {
                showToast(`Updated permissions for ${studentNumber} to ${newRole}`);
                loadUsers();
            });
        }

        loadScanners();
        loadUsers();
        setInterval(loadScanners, 3000);
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


# --- STUDENT LOGIN CLIENT INTEGRATION ---
@app.route("/api/heartbeat", methods=["POST"])
def student_heartbeat():
    """Endpoint consumed by silent_heartbeat() script running on student devices."""
    data = request.json or {}
    raw_student_id = str(data.get("student_id", "")).strip()
    location = data.get("location", "Unknown Location")

    if not raw_student_id:
        return (
            jsonify({"status": "REJECTED", "message": "Missing student_id"}),
            400,
        )

    cleaned_id, _ = AttendanceAIEngine.clean_and_filter(raw_student_id)
    target_id = cleaned_id if cleaned_id else raw_student_id

    with get_db("users.db") as conn:
        c = conn.cursor()
        c.execute(
            "SELECT name, permission_level FROM users WHERE student_number = ?",
            (target_id,),
        )
        user = c.fetchone()

    name = user[0] if user else raw_student_id
    role = user[1] if user else "student"

    STUDENT_HEARTBEATS[target_id] = {
        "last_seen": datetime.now(),
        "location": location,
        "name": name,
    }

    log_general_access(
        f"ClientApp ({location})", target_id, name, role, "HEARTBEAT"
    )

    return jsonify(
        {
            "status": "SUCCESS",
            "message": "Heartbeat received",
            "student_id": target_id,
        }
    )


@app.route("/api/scanner_heartbeat", methods=["POST"])
def scanner_heartbeat():
    client_id = (
        f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    )
    rank, _ = get_scanner_info(client_id)
    SCANNER_HEARTBEATS[rank] = datetime.now()
    return jsonify({"status": "OK"})


@app.route("/api/scanner_info", methods=["GET"])
def scanner_info():
    client_id = (
        f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    )
    rank, module = get_scanner_info(client_id)
    return jsonify({"scanner_id": rank, "module": module})


@app.route("/api/validate", methods=["POST"])
def validate():
    data = request.json or {}
    raw_number = data.get("barcode", "")

    client_id = (
        f"{request.remote_addr}_{hash(request.headers.get('User-Agent', ''))}"
    )
    rank, module = get_scanner_info(client_id)

    student_number, err = AttendanceAIEngine.clean_and_filter(raw_number)
    if err:
        return jsonify({"status": "REJECTED", "message": err})

    with get_db("users.db") as conn:
        c_u = conn.cursor()
        c_u.execute(
            "SELECT name, permission_level FROM users WHERE student_number = ?",
            (student_number,),
        )
        user = c_u.fetchone()

    if not user:
        return jsonify(
            {"status": "REJECTED", "message": "User not registered in database."}
        )

    name, permission_level = user

    is_anomaly, anomaly_msg = AttendanceAIEngine.detect_anomaly(
        student_number, permission_level
    )
    status_entry = "ANOMALY" if is_anomaly else "PRESENT"

    log_general_access(
        f"Scanner #{rank} ({module})",
        student_number,
        name,
        permission_level,
        status_entry,
    )

    if permission_level.lower() not in EXCLUDED_ROLES and not is_anomaly:
        log_subject_attendance(
            module, student_number, name, permission_level, status_entry
        )

    if is_anomaly:
        return jsonify({"status": "REJECTED", "message": anomaly_msg})

    return jsonify(
        {
            "status": "SUCCESS",
            "name": name,
            "role": permission_level,
            "module": module,
            "scanner_id": rank,
        }
    )


# --- ADMIN CONTROLLER API ---
@app.route("/api/admin/scanners", methods=["GET", "POST"])
def handle_admin_scanners():
    if request.method == "GET":
        with get_db("users.db") as conn:
            conn.row_factory = sqlite3.Row
            scanners = conn.execute(
                "SELECT scanner_id, module FROM scanner_config ORDER BY scanner_id ASC"
            ).fetchall()

        now = datetime.now()
        scanner_list = []
        for s in scanners:
            s_dict = dict(s)
            s_id = s_dict["scanner_id"]
            last_seen = SCANNER_HEARTBEATS.get(s_id)
            s_dict["active"] = (
                last_seen is not None and (now - last_seen).total_seconds() < 12
            )
            scanner_list.append(s_dict)

        return jsonify(scanner_list)

    elif request.method == "POST":
        data = request.json or {}
        scanner_id = data.get("scanner_id")
        module = data.get("module")

        with get_db("users.db") as conn:
            conn.execute(
                "INSERT OR REPLACE INTO scanner_config (scanner_id, module) VALUES (?, ?)",
                (scanner_id, module),
            )

        init_subject_db(module)
        return jsonify({"status": "SUCCESS"})


@app.route("/api/admin/users", methods=["GET", "POST"])
def handle_admin_users():
    if request.method == "GET":
        with get_db("users.db") as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute(
                "SELECT student_number, name, permission_level FROM users ORDER BY student_number ASC"
            ).fetchall()
        return jsonify([dict(u) for u in users])

    elif request.method == "POST":
        data = request.json or {}
        student_number = data.get("student_number")
        permission_level = data.get("permission_level")

        with get_db("users.db") as conn:
            conn.execute(
                "UPDATE users SET permission_level = ? WHERE student_number = ?",
                (permission_level, student_number),
            )
        return jsonify({"status": "SUCCESS"})


# --- LOGGING HELPERS ---
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
            users = conn.execute(
                "SELECT student_number, name, permission_level FROM users WHERE LOWER(permission_level) NOT IN ('admin', 'staff')"
            ).fetchall()

        attendance_map = {}
        if module:
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
# 6. DESKTOP MONITOR WINDOWS
# ==========================================
def run_db_viewer():
    root = tk.Tk()
    root.title("👥 Users Database (users.db)")
    root.geometry("500x300+50+150")

    frame_u = ttk.Frame(root, padding=10)
    frame_u.pack(fill="both", expand=True)
    tree_u = ttk.Treeview(
        frame_u, columns=("num", "name", "role"), show="headings"
    )
    for col in ("num", "name", "role"):
        tree_u.heading(col, text=col.capitalize())
        tree_u.column(col, anchor="center")
    tree_u.pack(fill="both", expand=True)

    logs_window = tk.Toplevel(root)
    logs_window.title("📋 Real-Time Access Logs (logs.db)")
    logs_window.geometry("750x300+600+150")

    frame_l = ttk.Frame(logs_window, padding=10)
    frame_l.pack(fill="both", expand=True)
    tree_l = ttk.Treeview(
        frame_l,
        columns=("id", "scanner", "num", "name", "role", "time", "status"),
        show="headings",
    )
    for col in ("id", "scanner", "num", "name", "role", "time", "status"):
        tree_l.heading(col, text=col.capitalize())
        tree_l.column(col, width=100, anchor="center")
    tree_l.pack(fill="both", expand=True)

    def auto_refresh():
        try:
            with sqlite3.connect("users.db", timeout=1.0) as conn:
                rows = conn.execute(
                    "SELECT student_number, name, permission_level FROM users"
                ).fetchall()
                tree_u.delete(*tree_u.get_children())
                for r in rows:
                    tree_u.insert("", "end", values=r)

            with sqlite3.connect("logs.db", timeout=1.0) as conn:
                logs = conn.execute(
                    "SELECT id, scanner_id, student_number, name, permission_level, timestamp, status FROM logs ORDER BY id DESC LIMIT 50"
                ).fetchall()
                tree_l.delete(*tree_l.get_children())
                for l_row in logs:
                    tree_l.insert("", "end", values=l_row)
        except Exception:
            pass
        root.after(2000, auto_refresh)

    auto_refresh()
    root.mainloop()


# ==========================================
# 7. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    init_dbs()
    print_terminal_qr(SERVER_URL)

    # Launch GUI in background thread
    gui_thread = threading.Thread(target=run_db_viewer, daemon=True)
    gui_thread.start()

    # Flask App Server (supports adhoc self-signed HTTPS context for testing)
    app.run(host="0.0.0.0", port=5000, ssl_context="adhoc")
