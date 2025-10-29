from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort
from functools import wraps
from datetime import datetime
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = 'replace-with-a-secure-random-key'
app.static_folder = 'static'

# MySQL config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'sk_ims_database'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Upload directories
UPLOAD_BASE = os.path.join(app.static_folder, 'uploads')
PROJECT_UPLOADS = os.path.join(UPLOAD_BASE, 'projects')
REPORT_UPLOADS = os.path.join(UPLOAD_BASE, 'reports')
os.makedirs(PROJECT_UPLOADS, exist_ok=True)
os.makedirs(REPORT_UPLOADS, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'xlsx', 'csv'}

mysql = MySQL(app)


# --- Helpers ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session['user']['role'] != role and session['user']['role'] != 'super_admin':
                flash('Access denied', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# --- Dashboard statistics ---
def get_dashboard_stats():
    cur = mysql.connection.cursor()

    cur.execute("SELECT status, COUNT(*) AS count FROM projects GROUP BY status")
    project_data = cur.fetchall()

    cur.execute("""
        SELECT DATE(date) AS log_date, COUNT(*) AS count
        FROM logbook
        WHERE MONTH(date)=MONTH(CURRENT_DATE()) AND YEAR(date)=YEAR(CURRENT_DATE())
        GROUP BY DATE(date)
        ORDER BY DATE(date)
    """)
    logbook_data = cur.fetchall()

    cur.execute("SELECT type, COUNT(*) AS count FROM reports GROUP BY type")
    report_data = cur.fetchall()

    cur.close()
    return project_data, logbook_data, report_data


def get_user_stats(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) AS total_projects FROM projects WHERE created_by=%s", (user_id,))
    proj = cur.fetchone()['total_projects'] if cur.rowcount else 0
    cur.execute("SELECT COUNT(*) AS total_reports FROM reports WHERE created_by=%s", (user_id,))
    rep = cur.fetchone()['total_reports'] if cur.rowcount else 0
    cur.close()
    return proj, rep


# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')


# --- LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'fullname': user['fullname'],
                'role': user['role']
            }
            flash(f"Welcome, {user['fullname']}", 'success')

            role = user['role']
            if role == 'super_admin':
                return redirect(url_for('superadmin_dashboard'))
            elif role == 'SK_Chairman':
                return redirect(url_for('sk_chairman_dashboard'))
            elif role == 'Secretary':
                return redirect(url_for('secretary_dashboard'))
            elif role == 'Treasurer':
                return redirect(url_for('treasurer_dashboard'))
            elif role == 'BMO':
                return redirect(url_for('bmo_dashboard'))
            else:
                return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))


# --- SUPER ADMIN ---
@app.route('/superadmin')
@login_required(role='super_admin')
def superadmin_dashboard():
    project_data, logbook_data, report_data = get_dashboard_stats()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    cur.close()
    return render_template(
        'dashboard_base.html',
        users=users,
        project_data=project_data,
        logbook_data=logbook_data,
        report_data=report_data,
        user_projects=user_projects,
        user_reports=user_reports
    )


# --- USER MANAGEMENT (Super Admin Only) ---
@app.route('/user_management')
@login_required(role='super_admin')
def user_management():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users = cur.fetchall()
    cur.close()
    return render_template('super_admin/user_management.html', users=users)


@app.route('/user_management/add', methods=['GET', 'POST'])
@login_required(role='super_admin')
def add_user():
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        if not fullname or not username or not password or not role:
            flash('All fields are required', 'danger')
            return redirect(url_for('add_user'))

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (fullname, username, password, role) VALUES (%s, %s, %s, %s)",
                    (fullname, username, password, role))
        mysql.connection.commit()
        cur.close()
        flash('User added successfully!', 'success')
        return redirect(url_for('user_management'))

    return render_template('super_admin/add_user.html')


@app.route('/user_management/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required(role='super_admin')
def edit_user_account(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not user:
        flash('User not found', 'danger')
        cur.close()
        return redirect(url_for('user_management'))

    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        if not fullname or not username or not role:
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('edit_user_account', user_id=user_id))

        if password:
            cur.execute("UPDATE users SET fullname=%s, username=%s, password=%s, role=%s WHERE id=%s",
                        (fullname, username, password, role, user_id))
        else:
            cur.execute("UPDATE users SET fullname=%s, username=%s, role=%s WHERE id=%s",
                        (fullname, username, role, user_id))

        mysql.connection.commit()
        cur.close()
        flash('User updated successfully!', 'success')
        return redirect(url_for('user_management'))

    cur.close()
    return render_template('super_admin/edit_user.html', user=user)


@app.route('/user_management/delete/<int:user_id>')
@login_required(role='super_admin')
def delete_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('user_management'))



# --- PROJECTS ---
@app.route('/projects')
@login_required()
def projects():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM projects ORDER BY start_date DESC')
    projects = cur.fetchall()
    cur.close()
    return render_template('projects.html', projects=projects)


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required()
def project_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date') or None
        end_date = request.form.get('end_date') or None
        details = request.form.get('details', '').strip()
        status = request.form.get('status', 'Planned').strip()
        file = request.files.get('file')

        if not name:
            flash('Project name is required', 'danger')
            return redirect(url_for('project_new'))

        filename_db = None
        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(PROJECT_UPLOADS, safe)
                file.save(dest)
                filename_db = f'uploads/projects/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('project_new'))

        cur = mysql.connection.cursor()
        cur.execute(
            'INSERT INTO projects (name, start_date, end_date, details, status, filename, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s)',
            (name, start_date, end_date, details, status, filename_db, session['user']['id'])
        )
        mysql.connection.commit()
        cur.close()
        flash('Project added', 'success')
        return redirect(url_for('projects'))
    return render_template('project_new.html')


@app.route('/projects/edit/<int:proj_id>', methods=['GET', 'POST'])
@login_required()
def project_edit(proj_id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date') or None
        end_date = request.form.get('end_date') or None
        details = request.form.get('details', '').strip()
        status = request.form.get('status', 'Planned').strip()
        file = request.files.get('file')

        if not name:
            flash('Project name is required', 'danger')
            return redirect(url_for('project_edit', proj_id=proj_id))

        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(PROJECT_UPLOADS, safe)
                file.save(dest)
                filename_db = f'uploads/projects/{safe}'
                cur.execute('UPDATE projects SET filename=%s WHERE id=%s', (filename_db, proj_id))
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('project_edit', proj_id=proj_id))

        cur.execute(
            'UPDATE projects SET name=%s, start_date=%s, end_date=%s, details=%s, status=%s WHERE id=%s',
            (name, start_date, end_date, details, status, proj_id)
        )
        mysql.connection.commit()
        cur.close()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects'))

    cur.execute('SELECT * FROM projects WHERE id=%s', (proj_id,))
    project = cur.fetchone()
    cur.close()

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    return render_template('project_edit.html', project=project)


@app.route('/projects/delete/<int:proj_id>')
@login_required()
def project_delete(proj_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM projects WHERE id=%s', (proj_id,))
    project = cur.fetchone()

    if not project:
        flash('Project not found', 'danger')
        cur.close()
        return redirect(url_for('projects'))

    cur.execute('DELETE FROM projects WHERE id=%s', (proj_id,))
    mysql.connection.commit()
    cur.close()

    if project.get('filename'):
        file_path = os.path.join(app.static_folder, project['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: could not delete file {file_path}: {e}")

    flash('Project deleted successfully!', 'info')
    return redirect(url_for('projects'))


# --- LOGBOOK ---
@app.route('/logbook', methods=['GET', 'POST'])
@login_required()
def logbook():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        middle = request.form.get('middle_name', '').strip()
        last = request.form.get('last_name', '').strip()
        sitio = request.form.get('sitio', '').strip()
        time_in = request.form.get('time_in') or None
        time_out = request.form.get('time_out') or None
        date = request.form.get('date') or None
        concern = request.form.get('concern', '').strip()

        if not first or not last or not date:
            flash('Please fill First Name, Last Name and Date', 'danger')
        else:
            cur.execute(
                'INSERT INTO logbook (first_name, middle_name, last_name, sitio, time_in, time_out, date, concern) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (first, middle, last, sitio, time_in, time_out, date, concern)
            )
            mysql.connection.commit()
            flash('Logbook entry added successfully!', 'success')

    cur.execute('SELECT * FROM logbook ORDER BY date DESC, id DESC')
    entries = cur.fetchall()
    cur.close()

    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    return render_template('logbook.html', entries=entries, sitios=sitios)


@app.route('/logbook/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required()
def logbook_edit(entry_id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        middle = request.form.get('middle_name', '').strip()
        last = request.form.get('last_name', '').strip()
        sitio = request.form.get('sitio', '').strip()
        time_in = request.form.get('time_in') or None
        time_out = request.form.get('time_out') or None
        date = request.form.get('date') or None
        concern = request.form.get('concern', '').strip()

        if not first or not last or not date:
            flash('Please fill First Name, Last Name and Date', 'danger')
        else:
            cur.execute('''
                UPDATE logbook
                SET first_name=%s, middle_name=%s, last_name=%s, sitio=%s,
                    time_in=%s, time_out=%s, date=%s, concern=%s
                WHERE id=%s
            ''', (first, middle, last, sitio, time_in, time_out, date, concern, entry_id))
            mysql.connection.commit()
            flash('Logbook entry updated successfully!', 'success')
            cur.close()
            return redirect(url_for('logbook'))

    cur.execute('SELECT * FROM logbook WHERE id=%s', (entry_id,))
    entry = cur.fetchone()
    cur.close()
    if not entry:
        flash('Logbook entry not found', 'danger')
        return redirect(url_for('logbook'))

    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    return render_template('logbook_edit.html', entry=entry, sitios=sitios)


@app.route('/logbook/delete/<int:entry_id>')
@login_required()
def logbook_delete(entry_id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM logbook WHERE id=%s', (entry_id,))
    mysql.connection.commit()
    cur.close()
    flash('Logbook entry deleted successfully!', 'info')
    return redirect(url_for('logbook'))


# --- REPORTS ---
@app.route('/reports')
@login_required()
def reports():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM reports ORDER BY uploaded_at DESC')
    reports = cur.fetchall()
    cur.close()
    return render_template('reports.html', reports=reports)


@app.route('/reports/new', methods=['GET', 'POST'])
@login_required()
def report_new():
    if request.method == 'POST':
        rtype = request.form.get('type', '').strip()
        reported_for = request.form.get('reported_for', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')

        if not rtype or not reported_for:
            flash('Please fill Type and Reported For', 'danger')
            return redirect(url_for('report_new'))

        filename_db = None
        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(REPORT_UPLOADS, safe)
                file.save(dest)
                filename_db = f'uploads/reports/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('report_new'))

        uploaded_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cur = mysql.connection.cursor()
        cur.execute(
            'INSERT INTO reports (type, filename, uploaded_at, reported_for, notes, created_by) VALUES (%s,%s,%s,%s,%s,%s)',
            (rtype, filename_db, uploaded_at, reported_for, notes, session['user']['id'])
        )
        mysql.connection.commit()
        cur.close()
        flash('Report registered', 'success')
        return redirect(url_for('reports'))

    return render_template('report_edit.html')


@app.route('/reports/edit/<int:rep_id>', methods=['GET', 'POST'])
@login_required()
def report_edit(rep_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM reports WHERE id=%s', (rep_id,))
    report = cur.fetchone()

    if not report:
        flash('Report not found', 'danger')
        cur.close()
        return redirect(url_for('reports'))

    if request.method == 'POST':
        rtype = request.form.get('type', '').strip()
        reported_for = request.form.get('reported_for', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')

        filename_db = report['filename']
        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(REPORT_UPLOADS, safe)
                file.save(dest)
                filename_db = f'uploads/reports/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('report_edit', rep_id=rep_id))

        cur.execute(
            'UPDATE reports SET type=%s, reported_for=%s, notes=%s, filename=%s WHERE id=%s',
            (rtype, reported_for, notes, filename_db, rep_id)
        )
        mysql.connection.commit()
        cur.close()
        flash('Report updated successfully!', 'success')
        return redirect(url_for('reports'))

    cur.close()
    return render_template('report_edit.html', report=report)


@app.route('/reports/delete/<int:rep_id>')
@login_required()
def report_delete(rep_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM reports WHERE id=%s', (rep_id,))
    report = cur.fetchone()

    if not report:
        flash('Report not found', 'danger')
        cur.close()
        return redirect(url_for('reports'))

    cur.execute('DELETE FROM reports WHERE id=%s', (rep_id,))
    mysql.connection.commit()
    cur.close()

    if report.get('filename'):
        file_path = os.path.join(app.static_folder, report['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: could not delete file {file_path}: {e}")

    flash('Report deleted successfully!', 'info')
    return redirect(url_for('reports'))


# --- DASHBOARDS WITH CHARTS ---
@app.route('/chairman')
@login_required(role='SK_Chairman')
def sk_chairman_dashboard():
    project_data, logbook_data, report_data = get_dashboard_stats()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    return render_template('dashboard_base.html',
                           project_data=project_data,
                           logbook_data=logbook_data,
                           report_data=report_data,
                           user_projects=user_projects,
                           user_reports=user_reports)


@app.route('/secretary')
@login_required(role='Secretary')
def secretary_dashboard():
    project_data, logbook_data, report_data = get_dashboard_stats()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    return render_template('dashboard_base.html',
                           project_data=project_data,
                           logbook_data=logbook_data,
                           report_data=report_data,
                           user_projects=user_projects,
                           user_reports=user_reports)


@app.route('/treasurer')
@login_required(role='Treasurer')
def treasurer_dashboard():
    project_data, logbook_data, report_data = get_dashboard_stats()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    return render_template('dashboard_base.html',
                           project_data=project_data,
                           logbook_data=logbook_data,
                           report_data=report_data,
                           user_projects=user_projects,
                           user_reports=user_reports)


@app.route('/bmo')
@login_required(role='BMO')
def bmo_dashboard():
    project_data, logbook_data, report_data = get_dashboard_stats()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    return render_template('dashboard_base.html',
                           project_data=project_data,
                           logbook_data=logbook_data,
                           report_data=report_data,
                           user_projects=user_projects,
                           user_reports=user_reports)


# --- FIX FILE VIEW ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve files correctly from static/uploads."""
    safe_path = os.path.join(app.static_folder, 'uploads')
    return send_from_directory(safe_path, filename, as_attachment=False)


# --- Run ---
if __name__ == '__main__':
    app.run(debug=True)
