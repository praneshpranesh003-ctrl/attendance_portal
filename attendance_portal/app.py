from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, date
import json
import os
import uuid

app = Flask(__name__, template_folder='data/templates')
app.secret_key = 'attendance_portal_secret_2024'

# ─── Data Storage (JSON files) ───────────────────────────────────────────────
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.json')
GATEPASSES_FILE = os.path.join(DATA_DIR, 'gatepasses.json')


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return default
    return default


def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


# Initialize data files with defaults
def init_data_files():
    default_users = {
        'admin': {
            'id': 'admin',
            'name': 'Administrator',
            'role': 'admin',
            'password': 'admin123',
            'email': 'admin@college.edu'
        }
    }
    if not os.path.exists(USERS_FILE):
        save_json(USERS_FILE, default_users)
    if not os.path.exists(ATTENDANCE_FILE):
        save_json(ATTENDANCE_FILE, {})
    if not os.path.exists(GATEPASSES_FILE):
        save_json(GATEPASSES_FILE, [])


def get_users():
    return load_json(USERS_FILE, {
        'admin': {
            'id': 'admin',
            'name': 'Administrator',
            'role': 'admin',
            'password': 'admin123',
            'email': 'admin@college.edu'
        }
    })


def get_attendance():
    return load_json(ATTENDANCE_FILE, {})


def get_gatepasses():
    return load_json(GATEPASSES_FILE, [])


# ─── Auth Helpers ─────────────────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─── Initialize Data Files ──────────────────────────────────────────────────
init_data_files()

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '').strip()
        users = get_users()

        user = None
        for uid, u in users.items():
            if (u.get('roll_number') == identifier or uid == identifier or u.get('email') == identifier) and u['password'] == password:
                user = u
                break

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        password = request.form.get('password', '').strip()
        student_type = request.form.get('student_type', 'day_scholar')  # 'hosteler' or 'day_scholar'
        department = request.form.get('department', '').strip()
        year = request.form.get('year', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        users = get_users()

        # Check duplicate roll number
        for uid, u in users.items():
            if u.get('roll_number') == roll_number:
                flash('Roll number already registered.', 'error')
                return render_template('login.html')

        user_id = str(uuid.uuid4())[:8]
        users[user_id] = {
            'id': user_id,
            'name': name,
            'roll_number': roll_number,
            'password': password,
            'role': 'student',
            'student_type': student_type,
            'department': department,
            'year': year,
            'email': email,
            'phone': phone,
            'created_at': datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─── Student Routes ───────────────────────────────────────────────────────────

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    users = get_users()
    attendance = get_attendance()
    gatepasses = get_gatepasses()
    user = users.get(session['user_id'], {})
    uid = session['user_id']

    # Calculate attendance stats
    user_att = attendance.get(uid, {})
    total_classes = sum(len(v) for v in user_att.values())
    present_count = sum(
        1 for subject_records in user_att.values()
        for record in subject_records.values()
        if record == 'present'
    )
    att_percentage = round((present_count / total_classes * 100) if total_classes > 0 else 0, 1)

    # Subject-wise
    subject_stats = {}
    for subject, records in user_att.items():
        total = len(records)
        present = sum(1 for v in records.values() if v == 'present')
        subject_stats[subject] = {
            'total': total,
            'present': present,
            'percentage': round((present / total * 100) if total > 0 else 0, 1)
        }

    # My gate passes
    my_passes = [gp for gp in gatepasses if gp.get('student_id') == uid]

    return render_template('student_dashboard.html',
                           user=user,
                           att_percentage=att_percentage,
                           present_count=present_count,
                           total_classes=total_classes,
                           subject_stats=subject_stats,
                           my_passes=my_passes)


@app.route('/student/gatepass', methods=['GET', 'POST'])
@login_required
def request_gatepass():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    users = get_users()
    user = users.get(session['user_id'], {})

    if user.get('student_type') != 'hosteler':
        flash('Gate pass is only for hostelers.', 'error')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        gatepasses = get_gatepasses()
        gp = {
            'id': str(uuid.uuid4())[:8],
            'student_id': session['user_id'],
            'student_name': session['name'],
            'roll_number': user.get('roll_number', ''),
            'reason': request.form.get('reason', '').strip(),
            'destination': request.form.get('destination', '').strip(),
            'departure_date': request.form.get('departure_date', ''),
            'return_date': request.form.get('return_date', ''),
            'contact': request.form.get('contact', '').strip(),
            'status': 'pending',
            'requested_at': datetime.now().isoformat(),
            'admin_remark': ''
        }
        gatepasses.append(gp)
        save_json(GATEPASSES_FILE, gatepasses)
        flash('Gate pass request submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('gatepass_form.html', user=user)


# ─── Admin Routes ─────────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    users = get_users()
    attendance = get_attendance()
    gatepasses = get_gatepasses()

    students = {uid: u for uid, u in users.items() if u.get('role') == 'student'}
    hostelers = sum(1 for u in students.values() if u.get('student_type') == 'hosteler')
    day_scholars = sum(1 for u in students.values() if u.get('student_type') == 'day_scholar')
    pending_passes = [gp for gp in gatepasses if gp.get('status') == 'pending']

    # Overall attendance
    all_present = 0
    all_total = 0
    for uid, subj_map in attendance.items():
        for subj, records in subj_map.items():
            all_total += len(records)
            all_present += sum(1 for v in records.values() if v == 'present')
    overall_att = round((all_present / all_total * 100) if all_total > 0 else 0, 1)

    return render_template('admin_dashboard.html',
                           students=students,
                           hostelers=hostelers,
                           day_scholars=day_scholars,
                           pending_passes=pending_passes,
                           overall_att=overall_att,
                           total_students=len(students))


@app.route('/admin/students')
@admin_required
def admin_students():
    users = get_users()
    attendance = get_attendance()
    students = {uid: u for uid, u in users.items() if u.get('role') == 'student'}

    student_list = []
    for uid, u in students.items():
        user_att = attendance.get(uid, {})
        total = sum(len(v) for v in user_att.values())
        present = sum(1 for sv in user_att.values() for v in sv.values() if v == 'present')
        att_pct = round((present / total * 100) if total > 0 else 0, 1)
        student_list.append({**u, 'att_percentage': att_pct, 'total_classes': total})

    return render_template('admin_students.html', students=student_list)


@app.route('/admin/attendance', methods=['GET', 'POST'])
@admin_required
def admin_attendance():
    users = get_users()
    students = {uid: u for uid, u in users.items() if u.get('role') == 'student'}

    if request.method == 'POST':
        attendance = get_attendance()
        subject = request.form.get('subject', '').strip()
        att_date = request.form.get('att_date', str(date.today()))

        for uid in students:
            status = request.form.get(f'status_{uid}', 'absent')
            if uid not in attendance:
                attendance[uid] = {}
            if subject not in attendance[uid]:
                attendance[uid][subject] = {}
            attendance[uid][subject][att_date] = status

        save_json(ATTENDANCE_FILE, attendance)
        flash(f'Attendance marked for {subject} on {att_date}', 'success')
        return redirect(url_for('admin_attendance'))

    return render_template('admin_attendance.html', students=students, today=str(date.today()))


@app.route('/admin/gatepasses')
@admin_required
def admin_gatepasses():
    gatepasses = get_gatepasses()
    return render_template('admin_gatepasses.html', gatepasses=gatepasses)


@app.route('/admin/gatepass/<gp_id>/action', methods=['POST'])
@admin_required
def gatepass_action(gp_id):
    action = request.form.get('action')
    remark = request.form.get('remark', '')
    gatepasses = get_gatepasses()

    for gp in gatepasses:
        if gp['id'] == gp_id:
            gp['status'] = 'approved' if action == 'approve' else 'rejected'
            gp['admin_remark'] = remark
            gp['reviewed_at'] = datetime.now().isoformat()
            break

    save_json(GATEPASSES_FILE, gatepasses)
    flash(f'Gate pass {action}d successfully.', 'success')
    return redirect(url_for('admin_gatepasses'))


@app.route('/admin/student/<uid>')
@admin_required
def admin_student_detail(uid):
    users = get_users()
    attendance = get_attendance()
    user = users.get(uid)
    if not user or user.get('role') != 'student':
        flash('Student not found.', 'error')
        return redirect(url_for('admin_students'))

    user_att = attendance.get(uid, {})
    subject_stats = {}
    for subject, records in user_att.items():
        total = len(records)
        present = sum(1 for v in records.values() if v == 'present')
        subject_stats[subject] = {
            'total': total,
            'present': present,
            'percentage': round((present / total * 100) if total > 0 else 0, 1),
            'records': records
        }

    return render_template('admin_student_detail.html', student=user, subject_stats=subject_stats)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route('/api/attendance/summary')
@login_required
def api_attendance_summary():
    attendance = get_attendance()
    uid = session['user_id']
    user_att = attendance.get(uid, {})
    result = []
    for subject, records in user_att.items():
        total = len(records)
        present = sum(1 for v in records.values() if v == 'present')
        result.append({
            'subject': subject,
            'total': total,
            'present': present,
            'percentage': round((present / total * 100) if total > 0 else 0, 1)
        })
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)