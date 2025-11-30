from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, jsonify
from functools import wraps
from datetime import datetime, date, timedelta
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename
from collections import defaultdict

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
LOGBOOK_EVIDENCE_UPLOADS = os.path.join(UPLOAD_BASE, 'logbook_evidence')
os.makedirs(PROJECT_UPLOADS, exist_ok=True)
os.makedirs(REPORT_UPLOADS, exist_ok=True)
os.makedirs(LOGBOOK_EVIDENCE_UPLOADS, exist_ok=True)  # This matches your existing folder

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


# Helper function to get available reports for linking
def get_available_reports(project_id):
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT r.* FROM reports r
        WHERE r.id NOT IN (
            SELECT pr.report_id FROM project_reports pr WHERE pr.project_id=%s
        )
        ORDER BY r.uploaded_at DESC
    ''', (project_id,))
    reports = cur.fetchall()
    cur.close()
    return reports


# Helper function to get available projects for linking
def get_available_projects():
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, name, status FROM projects ORDER BY name')
    projects = cur.fetchall()
    cur.close()
    return projects


# --- Enhanced Dashboard Analytics ---
def get_dashboard_analytics():
    cur = mysql.connection.cursor()
    
    # Get basic counts
    cur.execute("SELECT COUNT(*) as count FROM projects")
    projects_total = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM projects WHERE approved_by_sk_chairman=1")
    projects_approved = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM projects WHERE status='On-going'")
    projects_ongoing = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM projects WHERE status='Completed'")
    projects_completed = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM projects WHERE status='Planned'")
    projects_planned = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM reports")
    reports_total = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM reports WHERE MONTH(uploaded_at)=MONTH(CURRENT_DATE()) AND YEAR(uploaded_at)=YEAR(CURRENT_DATE())")
    reports_this_month = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM logbook")
    logbook_total = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM logbook WHERE date=CURRENT_DATE()")
    logbook_today = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM users")
    users_total = cur.fetchone()['count']
    
    # Get user roles count
    cur.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
    roles_data = cur.fetchall()
    roles_count = defaultdict(int)
    for role_data in roles_data:
        roles_count[role_data['role']] = role_data['count']
    
    # Get report categories
    cur.execute("SELECT type, COUNT(*) as count FROM reports GROUP BY type")
    reports_by_type = cur.fetchall()
    report_categories = []
    report_counts = []
    for type_data in reports_by_type:
        report_categories.append(type_data['type'])
        report_counts.append(type_data['count'])
    
    # Get user contributions by role
    user_roles = ['SK_Chairman', 'Secretary', 'Treasurer', 'BMO', 'super_admin']
    user_contributions = []
    for role in user_roles:
        cur.execute("SELECT COUNT(*) as count FROM projects p JOIN users u ON p.created_by = u.id WHERE u.role=%s", (role,))
        count = cur.fetchone()['count']
        user_contributions.append(count)
    
    # Get logbook activity for last 7 days
    logbook_dates = []
    logbook_counts = []
    for i in range(6, -1, -1):
        date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        cur.execute("SELECT COUNT(*) as count FROM logbook WHERE date=%s", (date_str,))
        count = cur.fetchone()['count']
        logbook_dates.append((datetime.now() - timedelta(days=i)).strftime('%m/%d'))
        logbook_counts.append(count)
    
    cur.close()
    
    return {
        'projects_total': projects_total,
        'projects_approved': projects_approved,
        'projects_ongoing': projects_ongoing,
        'projects_completed': projects_completed,
        'projects_planned': projects_planned,
        'reports_total': reports_total,
        'reports_this_month': reports_this_month,
        'logbook_total': logbook_total,
        'logbook_today': logbook_today,
        'users_total': users_total,
        'roles_count': roles_count,
        'report_categories': report_categories,
        'report_counts': report_counts,
        'user_roles': user_roles,
        'user_contributions': user_contributions,
        'logbook_dates': logbook_dates,
        'logbook_counts': logbook_counts
    }

def get_recent_activities():
    """Get recent activities for the dashboard"""
    cur = mysql.connection.cursor()
    activities = []
    
    try:
        # Check if created_at column exists in projects table
        cur.execute("SHOW COLUMNS FROM projects LIKE 'created_at'")
        has_created_at = cur.fetchone() is not None
        
        # Recent projects - handle missing created_at column
        if has_created_at:
            cur.execute("SELECT name, created_at FROM projects ORDER BY created_at DESC LIMIT 5")
        else:
            # Use alternative ordering if created_at doesn't exist
            cur.execute("SELECT name FROM projects ORDER BY id DESC LIMIT 5")
        
        recent_projects = cur.fetchall()
        for project in recent_projects:
            if has_created_at:
                activities.append({
                    'type': 'project',
                    'description': f'New project created: {project["name"]}',
                    'time': project['created_at'].strftime('%H:%M') if project['created_at'] else 'N/A'
                })
            else:
                activities.append({
                    'type': 'project',
                    'description': f'Project: {project["name"]}',
                    'time': 'Recent'
                })
        
        # Recent reports
        cur.execute("SELECT type, uploaded_at FROM reports ORDER BY uploaded_at DESC LIMIT 5")
        recent_reports = cur.fetchall()
        for report in recent_reports:
            activities.append({
                'type': 'report',
                'description': f'New report uploaded: {report["type"]}',
                'time': report['uploaded_at'].strftime('%H:%M') if report['uploaded_at'] else 'N/A'
            })
        
        # Recent logbook entries
        cur.execute("SELECT first_name, last_name, date FROM logbook ORDER BY date DESC, id DESC LIMIT 5")
        recent_logbook = cur.fetchall()
        for entry in recent_logbook:
            activities.append({
                'type': 'logbook',
                'description': f'New logbook entry: {entry["first_name"]} {entry["last_name"]}',
                'time': entry['date'].strftime('%H:%M') if entry['date'] else 'N/A'
            })
    
    except Exception as e:
        print(f"Error getting recent activities: {e}")
        # Fallback activities if there's an error
        activities = [
            {
                'type': 'system',
                'description': 'System initialized',
                'time': datetime.now().strftime('%H:%M')
            }
        ]
    
    finally:
        cur.close()
    
    # Sort by time and return top 10
    return sorted(activities, key=lambda x: x['time'], reverse=True)[:10]


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
            # ✅ ADD SIDEBAR PARAMETER TO REDIRECT URLS
            if role == 'super_admin':
                return redirect(url_for('superadmin_dashboard') + '?sidebar=open')
            elif role == 'SK_Chairman':
                return redirect(url_for('sk_chairman_dashboard') + '?sidebar=open')
            elif role == 'Secretary':
                return redirect(url_for('secretary_dashboard') + '?sidebar=open')
            elif role == 'Treasurer':
                return redirect(url_for('treasurer_dashboard') + '?sidebar=open')
            elif role == 'BMO':
                return redirect(url_for('bmo_dashboard') + '?sidebar=open')
            else:
                return redirect(url_for('index') + '?sidebar=open')
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))


# --- ENHANCED DASHBOARD ---
@app.route('/dashboard')
@login_required()
def dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('dashboard_base.html',
                         recent_activities=recent_activities,
                         sidebar_open=sidebar_open,
                         **analytics)


# --- SUPER ADMIN ---
# --- SUPER ADMIN ---
@app.route('/superadmin')
@login_required(role='super_admin')
def superadmin_dashboard():
    # FIXED: Use enhanced analytics that includes roles_count
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    cur.close()
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template(
        'dashboard_base.html',
        users=users,
        recent_activities=recent_activities,
        user_projects=user_projects,
        user_reports=user_reports,
        sidebar_open=sidebar_open,
        **analytics  # ✅ PASS ALL ANALYTICS DATA INCLUDING roles_count
    )

# --- USER MANAGEMENT (Super Admin Only) ---
@app.route('/user_management')
@login_required(role='super_admin')
def user_management():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users = cur.fetchall()
    cur.close()
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('super_admin/user_management.html', users=users, sidebar_open=sidebar_open)


@app.route('/user_management/add', methods=['GET', 'POST'])
@login_required(role='super_admin')
def add_user():
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
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
        return redirect(url_for('user_management') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE

    return render_template('super_admin/add_user.html', sidebar_open=sidebar_open)


@app.route('/user_management/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required(role='super_admin')
def edit_user_account(user_id):
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
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
        return redirect(url_for('user_management') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE

    cur.close()
    return render_template('super_admin/edit_user.html', user=user, sidebar_open=sidebar_open)


@app.route('/user_management/delete/<int:user_id>')
@login_required(role='super_admin')
def delete_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('user_management') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE



# --- PROJECTS ---
@app.route('/projects')
@login_required()
def projects():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM projects ORDER BY start_date DESC')
    projects = cur.fetchall()
    cur.close()
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('projects.html', projects=projects, sidebar_open=sidebar_open)


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required()
def project_new():
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
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
        return redirect(url_for('projects') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE
    return render_template('project_new.html', sidebar_open=sidebar_open)


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
    return redirect(url_for('projects') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE


# --- PROJECT UPDATES & MANAGEMENT ---
@app.route('/projects/<int:proj_id>/updates', methods=['GET', 'POST'])
@login_required()
def project_updates(proj_id):
    cur = mysql.connection.cursor()
    
    # Handle POST request for project updates and edits
    if request.method == 'POST':
        # Check if this is a project update addition
        if 'add_update' in request.form:
            # This is a project update addition
            update_content = request.form.get('update_content', '').strip()
            update_date = request.form.get('update_date') or datetime.now().date()
            
            if not update_content:
                flash('Update content is required', 'danger')
                return redirect(url_for('project_updates', proj_id=proj_id))
            
            cur.execute(
                'INSERT INTO project_updates (project_id, update_text, update_date, created_by) VALUES (%s, %s, %s, %s)',
                (proj_id, update_content, update_date, session['user']['id'])
            )
            mysql.connection.commit()
            flash('Project update added successfully!', 'success')
            
        else:
            # This is a project edit
            name = request.form.get('name', '').strip()
            start_date = request.form.get('start_date') or None
            end_date = request.form.get('end_date') or None
            details = request.form.get('details', '').strip()
            status = request.form.get('status', 'Planned').strip()
            file = request.files.get('file')

            if not name:
                flash('Project name is required', 'danger')
                return redirect(url_for('project_updates', proj_id=proj_id))

            if file and file.filename:
                if allowed_file(file.filename):
                    safe = secure_filename(file.filename)
                    dest = os.path.join(PROJECT_UPLOADS, safe)
                    file.save(dest)
                    filename_db = f'uploads/projects/{safe}'
                    cur.execute('UPDATE projects SET filename=%s WHERE id=%s', (filename_db, proj_id))
                else:
                    flash('File type not allowed', 'danger')
                    return redirect(url_for('project_updates', proj_id=proj_id))

            cur.execute(
                'UPDATE projects SET name=%s, start_date=%s, end_date=%s, details=%s, status=%s WHERE id=%s',
                (name, start_date, end_date, details, status, proj_id)
            )
            mysql.connection.commit()
            flash('Project updated successfully!', 'success')
        
        return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')
    
    # GET request - show project updates page
    cur.execute('SELECT * FROM projects WHERE id=%s', (proj_id,))
    project = cur.fetchone()
    
    if not project:
        flash('Project not found', 'danger')
        cur.close()
        return redirect(url_for('projects'))
    
    # Get project updates
    cur.execute('''
        SELECT pu.*, u.fullname 
        FROM project_updates pu 
        JOIN users u ON pu.created_by = u.id 
        WHERE pu.project_id=%s 
        ORDER BY pu.update_date DESC, pu.created_at DESC
    ''', (proj_id,))
    updates = cur.fetchall()
    
    # Get associated reports
    cur.execute('''
        SELECT r.* FROM reports r
        JOIN project_reports pr ON r.id = pr.report_id
        WHERE pr.project_id=%s
        ORDER BY r.uploaded_at DESC
    ''', (proj_id,))
    reports = cur.fetchall()
    
    # Get available reports for linking
    available_reports = get_available_reports(proj_id)
    
    cur.close()
    
    sidebar_open = request.args.get('sidebar') == 'open'
    return render_template('project_updates.html', 
                         project=project, 
                         updates=updates, 
                         reports=reports,
                         available_reports=available_reports,
                         now=datetime.now(),
                         sidebar_open=sidebar_open)

# Edit project update
@app.route('/projects/<int:proj_id>/updates/<int:update_id>/edit', methods=['GET', 'POST'])
@login_required()
def edit_project_update(proj_id, update_id):
    cur = mysql.connection.cursor()
    
    # Get the update
    cur.execute('''
        SELECT pu.*, u.fullname 
        FROM project_updates pu 
        JOIN users u ON pu.created_by = u.id 
        WHERE pu.id=%s AND pu.project_id=%s
    ''', (update_id, proj_id))
    update = cur.fetchone()
    
    if not update:
        flash('Update not found', 'danger')
        cur.close()
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    # Check if user owns this update or is admin/SK Chairman
    if update['created_by'] != session['user']['id'] and session['user']['role'] not in ['super_admin', 'SK_Chairman']:
        flash('You can only edit your own updates', 'danger')
        cur.close()
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    if request.method == 'POST':
        update_content = request.form.get('update_content', '').strip()
        update_date = request.form.get('update_date') or datetime.now().date()
        
        if not update_content:
            flash('Update content is required', 'danger')
            return redirect(url_for('edit_project_update', proj_id=proj_id, update_id=update_id))
        
        cur.execute(
            'UPDATE project_updates SET update_text=%s, update_date=%s, updated_at=NOW() WHERE id=%s',
            (update_content, update_date, update_id)
        )
        mysql.connection.commit()
        cur.close()
        flash('Project update edited successfully!', 'success')
        return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')
    
    cur.close()
    
    sidebar_open = request.args.get('sidebar') == 'open'
    return render_template('edit_project_update.html', 
                         project_id=proj_id,
                         update=update,
                         now=datetime.now(),
                         sidebar_open=sidebar_open)

# Delete project update
@app.route('/projects/<int:proj_id>/updates/<int:update_id>/delete')
@login_required()
def delete_project_update(proj_id, update_id):
    cur = mysql.connection.cursor()
    
    # Get the update
    cur.execute('SELECT * FROM project_updates WHERE id=%s AND project_id=%s', (update_id, proj_id))
    update = cur.fetchone()
    
    if not update:
        flash('Update not found', 'danger')
        cur.close()
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    # Check if user owns this update or is admin/SK Chairman
    if update['created_by'] != session['user']['id'] and session['user']['role'] not in ['super_admin', 'SK_Chairman']:
        flash('You can only delete your own updates', 'danger')
        cur.close()
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    cur.execute('DELETE FROM project_updates WHERE id=%s', (update_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Project update deleted successfully!', 'info')
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

@app.route('/projects/<int:proj_id>/toggle_approval', methods=['POST'])
@login_required(role='SK_Chairman')
def toggle_project_approval(proj_id):
    cur = mysql.connection.cursor()
    
    # Get current approval status
    cur.execute('SELECT approved_by_sk_chairman FROM projects WHERE id=%s', (proj_id,))
    project = cur.fetchone()
    
    if not project:
        flash('Project not found', 'danger')
        cur.close()
        return redirect(url_for('projects'))
    
    new_status = not project['approved_by_sk_chairman']
    
    cur.execute(
        'UPDATE projects SET approved_by_sk_chairman=%s, approved_at=%s WHERE id=%s',
        (new_status, datetime.utcnow() if new_status else None, proj_id)
    )
    mysql.connection.commit()
    cur.close()
    
    status_text = "approved" if new_status else "unapproved"
    flash(f'Project {status_text} successfully!', 'success')
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

@app.route('/projects/<int:proj_id>/link_report', methods=['POST'])
@login_required()
def link_report_to_project(proj_id):
    report_id = request.form.get('report_id')
    
    if not report_id:
        flash('Please select a report', 'danger')
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    cur = mysql.connection.cursor()
    
    # Check if link already exists
    cur.execute('SELECT id FROM project_reports WHERE project_id=%s AND report_id=%s', (proj_id, report_id))
    existing = cur.fetchone()
    
    if not existing:
        cur.execute('INSERT INTO project_reports (project_id, report_id) VALUES (%s, %s)', (proj_id, report_id))
        mysql.connection.commit()
        flash('Report linked to project successfully!', 'success')
    else:
        flash('This report is already linked to the project', 'info')
    
    cur.close()
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

@app.route('/projects/<int:proj_id>/unlink_report/<int:report_id>')
@login_required()
def unlink_report_from_project(proj_id, report_id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM project_reports WHERE project_id=%s AND report_id=%s', (proj_id, report_id))
    mysql.connection.commit()
    cur.close()
    
    flash('Report unlinked from project successfully!', 'info')
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')


# --- LOGBOOK ---
@app.route('/logbook', methods=['GET', 'POST'])
@login_required()
def logbook():
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
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
        evidence_files = request.files.getlist('evidence')

        if not first or not last or not date:
            flash('Please fill First Name, Last Name and Date', 'danger')
        else:
            # Handle evidence file uploads
            evidence_filenames = []
            for file in evidence_files:
                if file and file.filename:
                    if allowed_file(file.filename):
                        safe = secure_filename(file.filename)
                        dest = os.path.join(LOGBOOK_EVIDENCE_UPLOADS, safe)
                        file.save(dest)
                        evidence_filenames.append(safe)
                    else:
                        flash(f'File type not allowed: {file.filename}', 'danger')
                        return redirect(url_for('logbook'))

            # Convert list to string for database storage
            evidence_db = ','.join(evidence_filenames) if evidence_filenames else None

            cur.execute(
                'INSERT INTO logbook (first_name, middle_name, last_name, sitio, time_in, time_out, date, concern, evidence_files) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (first, middle, last, sitio, time_in, time_out, date, concern, evidence_db)
            )
            mysql.connection.commit()
            flash('Logbook entry added successfully!', 'success')

    cur.execute('SELECT * FROM logbook ORDER BY date DESC, id DESC')
    entries = cur.fetchall()
    cur.close()

    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    return render_template('logbook.html', entries=entries, sitios=sitios, sidebar_open=sidebar_open)


@app.route('/logbook/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required()
def logbook_edit(entry_id):
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
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
        evidence_files = request.files.getlist('evidence')

        if not first or not last or not date:
            flash('Please fill First Name, Last Name and Date', 'danger')
        else:
            # Handle evidence file uploads for editing
            evidence_filenames = []
            for file in evidence_files:
                if file and file.filename:
                    if allowed_file(file.filename):
                        safe = secure_filename(file.filename)
                        dest = os.path.join(LOGBOOK_EVIDENCE_UPLOADS, safe)
                        file.save(dest)
                        evidence_filenames.append(safe)
                    else:
                        flash(f'File type not allowed: {file.filename}', 'danger')
                        return redirect(url_for('logbook_edit', entry_id=entry_id))

            # If new files were uploaded, update the evidence
            if evidence_filenames:
                evidence_db = ','.join(evidence_filenames)
                cur.execute('UPDATE logbook SET evidence_files=%s WHERE id=%s', (evidence_db, entry_id))

            cur.execute('''
                UPDATE logbook
                SET first_name=%s, middle_name=%s, last_name=%s, sitio=%s,
                    time_in=%s, time_out=%s, date=%s, concern=%s
                WHERE id=%s
            ''', (first, middle, last, sitio, time_in, time_out, date, concern, entry_id))
            mysql.connection.commit()
            flash('Logbook entry updated successfully!', 'success')
            cur.close()
            return redirect(url_for('logbook') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE

    cur.execute('SELECT * FROM logbook WHERE id=%s', (entry_id,))
    entry = cur.fetchone()
    cur.close()
    if not entry:
        flash('Logbook entry not found', 'danger')
        return redirect(url_for('logbook'))

    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    return render_template('logbook_edit.html', entry=entry, sitios=sitios, sidebar_open=sidebar_open)


@app.route('/logbook/delete/<int:entry_id>')
@login_required()
def logbook_delete(entry_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT evidence_files FROM logbook WHERE id=%s', (entry_id,))
    entry = cur.fetchone()
    
    # Delete associated evidence files
    if entry and entry['evidence_files']:
        evidence_files = entry['evidence_files'].split(',')
        for filename in evidence_files:
            file_path = os.path.join(LOGBOOK_EVIDENCE_UPLOADS, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Warning: could not delete evidence file {file_path}: {e}")

    cur.execute('DELETE FROM logbook WHERE id=%s', (entry_id,))
    mysql.connection.commit()
    cur.close()
    flash('Logbook entry deleted successfully!', 'info')
    return redirect(url_for('logbook') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE


@app.route('/logbook/evidence/<int:entry_id>')
@login_required()
def get_logbook_evidence(entry_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT evidence_files FROM logbook WHERE id=%s', (entry_id,))
    entry = cur.fetchone()
    cur.close()
    
    if entry and entry['evidence_files']:
        files = entry['evidence_files'].split(',')
        return {'evidence_files': files}
    return {'evidence_files': []}


@app.route('/uploads/logbook_evidence/<filename>')
def serve_logbook_evidence(filename):
    """Serve logbook evidence files from the correct directory"""
    return send_from_directory(LOGBOOK_EVIDENCE_UPLOADS, filename, as_attachment=False)


# --- REPORTS ---
@app.route('/reports')
@login_required()
def reports():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM reports ORDER BY uploaded_at DESC')
    reports_data = cur.fetchall()
    
    # Get linked projects for each report
    reports_with_projects = []
    for report in reports_data:
        cur.execute('''
            SELECT p.id, p.name, p.status FROM projects p
            JOIN project_reports pr ON p.id = pr.project_id
            WHERE pr.report_id=%s
        ''', (report['id'],))
        linked_projects = cur.fetchall()
        report['linked_projects'] = linked_projects
        reports_with_projects.append(report)
    
    cur.close()
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('reports.html', reports=reports_with_projects, sidebar_open=sidebar_open)


@app.route('/reports/new', methods=['GET', 'POST'])
@login_required()
def report_new():
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    if request.method == 'POST':
        rtype = request.form.get('type', '').strip()
        reported_for = request.form.get('reported_for', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')
        project_id = request.form.get('project_id')

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
        report_id = cur.lastrowid
        
        # Link to project if selected
        if project_id and project_id != '':
            cur.execute('INSERT INTO project_reports (project_id, report_id) VALUES (%s, %s)', (project_id, report_id))
        
        mysql.connection.commit()
        cur.close()
        flash('Report registered', 'success')
        return redirect(url_for('reports') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE

    available_projects = get_available_projects()
    return render_template('report_new.html', sidebar_open=sidebar_open, available_projects=available_projects)


@app.route('/reports/edit/<int:rep_id>', methods=['GET', 'POST'])
@login_required()
def report_edit(rep_id):
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM reports WHERE id=%s', (rep_id,))
    report = cur.fetchone()

    if not report:
        flash('Report not found', 'danger')
        cur.close()
        return redirect(url_for('reports'))

    # Get linked projects
    cur.execute('''
        SELECT p.* FROM projects p
        JOIN project_reports pr ON p.id = pr.project_id
        WHERE pr.report_id=%s
    ''', (rep_id,))
    linked_projects = cur.fetchall()

    if request.method == 'POST':
        rtype = request.form.get('type', '').strip()
        reported_for = request.form.get('reported_for', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')
        project_id = request.form.get('project_id')

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
        
        # Link to new project if selected
        if project_id and project_id != '':
            # Check if link already exists
            cur.execute('SELECT id FROM project_reports WHERE project_id=%s AND report_id=%s', (project_id, rep_id))
            existing = cur.fetchone()
            if not existing:
                cur.execute('INSERT INTO project_reports (project_id, report_id) VALUES (%s, %s)', (project_id, rep_id))
        
        mysql.connection.commit()
        cur.close()
        flash('Report updated successfully!', 'success')
        return redirect(url_for('reports') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE

    available_projects = get_available_projects()
    cur.close()
    return render_template('report_edit.html', report=report, sidebar_open=sidebar_open, 
                         available_projects=available_projects, linked_projects=linked_projects)


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
    return redirect(url_for('reports') + '?sidebar=open')  # ✅ PRESERVE SIDEBAR STATE


# --- DASHBOARDS WITH CHARTS ---
@app.route('/chairman')
@login_required(role='SK_Chairman')
def sk_chairman_dashboard():
    # FIXED: Get analytics data including roles_count
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         sidebar_open=sidebar_open,
                         **analytics)


@app.route('/secretary')
@login_required(role='Secretary')
def secretary_dashboard():
    # FIXED: Get analytics data including roles_count
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         sidebar_open=sidebar_open,
                         **analytics)


@app.route('/treasurer')
@login_required(role='Treasurer')
def treasurer_dashboard():
    # FIXED: Get analytics data including roles_count
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         sidebar_open=sidebar_open,
                         **analytics)


@app.route('/bmo')
@login_required(role='BMO')
def bmo_dashboard():
    # FIXED: Get analytics data including roles_count
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports = get_user_stats(session['user']['id'])
    
    # ✅ ADD SIDEBAR PARAMETER CHECK
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         sidebar_open=sidebar_open,
                         **analytics)


# --- FIX FILE VIEW ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve files correctly from static/uploads."""
    safe_path = os.path.join(app.static_folder, 'uploads')
    return send_from_directory(safe_path, filename, as_attachment=False)


# --- Run ---
if __name__ == '__main__':
    app.run(debug=True)