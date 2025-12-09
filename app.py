from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, jsonify
from functools import wraps
from datetime import datetime, date as date_module, timedelta
import os
from werkzeug.utils import secure_filename
from collections import defaultdict
from decimal import Decimal
import math
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.static_folder = 'static'

# --- Supabase Configuration ---
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://vrtkjoffsbgfzpkelyxh.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZydGtqb2Zmc2JnZnpwa2VseXhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUxNzE5NDksImV4cCI6MjA4MDc0Nzk0OX0.5qFthbgIm4XEZC_c9yqWXgsvbd7PtA9RmYf2582v8dg')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZydGtqb2Zmc2JnZnpwa2VseXhoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE3MTk0OSwiZXhwIjoyMDgwNzQ3OTQ5fQ.PAY24rwLf8xz3X97dkSYkJ145hF4d5uJG8EBhnSAu9s')

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected successfully!")
except Exception as e:
    print(f"❌ Supabase connection failed: {e}")
    supabase = None

# Pagination config
ITEMS_PER_PAGE = 10

# Upload directories
UPLOAD_BASE = os.path.join(app.static_folder, 'uploads')
PROJECT_UPLOADS = os.path.join(UPLOAD_BASE, 'projects')
REPORT_UPLOADS = os.path.join(UPLOAD_BASE, 'reports')
LOGBOOK_EVIDENCE_UPLOADS = os.path.join(UPLOAD_BASE, 'logbook_evidence')
BUDGET_EVIDENCE_UPLOADS = os.path.join(UPLOAD_BASE, 'budget_evidence')
os.makedirs(PROJECT_UPLOADS, exist_ok=True)
os.makedirs(REPORT_UPLOADS, exist_ok=True)
os.makedirs(LOGBOOK_EVIDENCE_UPLOADS, exist_ok=True)
os.makedirs(BUDGET_EVIDENCE_UPLOADS, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'xlsx', 'csv'}

# --- Helper function to parse datetime strings ---
def parse_datetime(date_str):
    """Safely parse datetime strings from various formats"""
    if not date_str:
        return None
    
    if isinstance(date_str, datetime):
        return date_str
    
    if isinstance(date_str, date_module):
        return datetime.combine(date_str, datetime.min.time())
    
    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try common date formats
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
    
    return None

# --- Supabase Helper Functions ---
def execute_query(table, action='select', filters=None, data=None, order_by=None, limit=None, offset=None):
    """Execute Supabase queries"""
    try:
        query = supabase.table(table)
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        
        if order_by:
            if isinstance(order_by, tuple):
                column, ascending = order_by
                if ascending:
                    query = query.order(column)
                else:
                    query = query.order(column, desc=True)
            elif isinstance(order_by, str):
                query = query.order(order_by, desc=True)
        
        if action == 'select':
            if limit:
                query = query.limit(limit)
            if offset is not None:
                # Supabase range is inclusive, so we need offset to offset+limit-1
                query = query.range(offset, offset + limit - 1 if limit else offset)
            result = query.execute()
            return result
        elif action == 'insert':
            result = supabase.table(table).insert(data).execute()
            return result
        elif action == 'update':
            if 'id' in data:
                return supabase.table(table).update(data).eq('id', data['id']).execute()
            elif filters and 'id' in filters:
                return supabase.table(table).update(data).eq('id', filters['id']).execute()
        elif action == 'delete':
            if filters and 'id' in filters:
                return supabase.table(table).delete().eq('id', filters['id']).execute()
    except Exception as e:
        print(f"Supabase query error for table {table}: {e}")
        # Return empty result
        class EmptyResult:
            data = []
            count = 0
        return EmptyResult()

def fetch_one(table, filters=None):
    """Fetch a single row"""
    try:
        query = supabase.table(table).select('*')
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        result = query.limit(1).execute()
        return result.data[0] if result.data and len(result.data) > 0 else None
    except Exception as e:
        print(f"Error fetching one from {table}: {e}")
        return None

def fetch_all(table, filters=None, order_by=None, limit=None, offset=None):
    """Fetch multiple rows with proper Supabase syntax"""
    try:
        query = supabase.table(table).select('*')
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        
        if order_by:
            if isinstance(order_by, tuple):
                column, ascending = order_by
                if ascending:
                    query = query.order(column)
                else:
                    query = query.order(column, desc=True)
            elif isinstance(order_by, str):
                query = query.order(order_by, desc=True)
        
        if limit:
            query = query.limit(limit)
        if offset is not None:
            # Supabase range is inclusive: range(start, end)
            end = offset + limit - 1 if limit else offset
            query = query.range(offset, end)
        
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching all from {table}: {e}")
        return []

def insert_data(table, data):
    """Insert data and return the inserted record"""
    try:
        result = supabase.table(table).insert(data).execute()
        if result.data and len(result.data) > 0:
            print(f"✅ Inserted into {table}, ID: {result.data[0].get('id')}")
            return result.data[0]
        else:
            print(f"⚠️ No data returned from insert into {table}")
            return None
    except Exception as e:
        print(f"❌ Error inserting data into {table}: {e}")
        return None

def update_data(table, id_value, data):
    """Update data by ID"""
    try:
        result = supabase.table(table).update(data).eq('id', id_value).execute()
        if result.data and len(result.data) > 0:
            print(f"✅ Updated {table} ID {id_value}")
            return result.data[0]
        else:
            print(f"⚠️ No data returned from update {table} ID {id_value}")
            return None
    except Exception as e:
        print(f"❌ Error updating data in {table}: {e}")
        return None

def delete_data(table, id_value):
    """Delete data by ID"""
    try:
        supabase.table(table).delete().eq('id', id_value).execute()
        print(f"✅ Deleted from {table} ID {id_value}")
        return True
    except Exception as e:
        print(f"❌ Error deleting from {table}: {e}")
        return False

def count_rows(table, filters=None):
    """Count rows in a table"""
    try:
        query = supabase.table(table).select('id', count='exact')
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        result = query.execute()
        return result.count if hasattr(result, 'count') and result.count is not None else 0
    except Exception as e:
        print(f"❌ Error counting rows in {table}: {e}")
        return 0

# --- Pagination Helper ---
def get_pagination_data(page, total_items, per_page=ITEMS_PER_PAGE):
    """Calculate pagination parameters"""
    if total_items <= 0:
        return {
            'current_page': 1,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': 1,
            'offset': 0,
            'has_prev': False,
            'has_next': False,
            'prev_page': 1,
            'next_page': 1,
            'page_range': [1],
            'show_pagination': False
        }
    
    total_pages = math.ceil(total_items / per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    
    return {
        'current_page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'offset': offset,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else 1,
        'next_page': page + 1 if page < total_pages else total_pages,
        'page_range': list(range(max(1, page - 2), min(total_pages + 1, page + 3))),
        'show_pagination': total_pages > 1
    }

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

# --- Budget Activity Logging Functions ---
def log_budget_activity(budget_id, description, performer_id=None, amount_changed=0, 
                       entry_type=None, old_balance=None, new_balance=None):
    """Log budget activity to the activity history table"""
    try:
        # Get performer info
        if not performer_id and 'user' in session:
            performer_id = session['user']['id']
        
        performer = fetch_one('users', {'id': performer_id}) if performer_id else None
        performer_name = performer.get('fullname', 'System') if performer else 'System'
        
        # Get budget info
        budget = fetch_one('budgets', {'id': budget_id}) if budget_id else None
        budget_name = budget.get('name', 'Unknown') if budget else 'Unknown'
        
        activity_data = {
            'budget_id': budget_id,
            'description': description,
            'performer_id': performer_id,
            'performer_name': performer_name,
            'performed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'amount_changed': float(amount_changed) if amount_changed else 0,
            'activity_type': entry_type if entry_type else 'budget_activity',
            'old_balance': float(old_balance) if old_balance is not None else None,
            'new_balance': float(new_balance) if new_balance is not None else None,
            'budget_name': budget_name
        }
        
        insert_data('budget_activity_history', activity_data)
        print(f"✅ Budget activity logged: {description}")
        return True
    except Exception as e:
        print(f"❌ Error logging budget activity: {e}")
        return False

def log_budget_entry_activity(entry_id, action, performer_id=None):
    """Log specific budget entry activities (create, approve, reject)"""
    try:
        entry = fetch_one('budget_entries', {'id': entry_id})
        if not entry:
            return False
        
        budget = fetch_one('budgets', {'id': entry['budget_id']}) if entry.get('budget_id') else None
        performer = fetch_one('users', {'id': performer_id}) if performer_id else None
        
        description = ""
        activity_type = ""
        
        if action == 'create':
            if entry.get('entry_type') == 'increase':
                description = f"Added budget increase of ₱{entry.get('amount', 0):.2f}: {entry.get('description', 'No description')}"
                activity_type = 'budget_increase'
            else:
                description = f"Requested budget expense of ₱{entry.get('amount', 0):.2f}: {entry.get('description', 'No description')}"
                activity_type = 'budget_expense'
        
        elif action == 'approve':
            if entry.get('entry_type') == 'increase':
                description = f"Approved budget increase of ₱{entry.get('amount', 0):.2f}: {entry.get('description', 'No description')}"
                activity_type = 'entry_approved'
            else:
                description = f"Approved budget expense of ₱{entry.get('amount', 0):.2f}: {entry.get('description', 'No description')}"
                activity_type = 'entry_approved'
        
        elif action == 'reject':
            description = f"Rejected budget entry: {entry.get('description', 'No description')}"
            activity_type = 'entry_rejected'
        
        activity_data = {
            'budget_id': entry['budget_id'],
            'description': description,
            'performer_id': performer_id,
            'performer_name': performer.get('fullname', 'System') if performer else 'System',
            'performed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'amount_changed': float(entry.get('amount', 0)) if action in ['create', 'approve'] else 0,
            'activity_type': activity_type,
            'old_balance': float(budget.get('current_balance', 0)) if budget else None,
            'new_balance': None,  # Will be updated after balance change
            'budget_name': budget.get('name', 'Unknown') if budget else 'Unknown'
        }
        
        insert_data('budget_activity_history', activity_data)
        return True
    except Exception as e:
        print(f"❌ Error logging budget entry activity: {e}")
        return False

# --- Dashboard statistics ---
def get_dashboard_stats():
    # Project status counts
    projects = fetch_all('projects')
    project_data = []
    status_counts = defaultdict(int)
    for project in projects:
        status_counts[project.get('status', 'Unknown')] += 1
    for status, count in status_counts.items():
        project_data.append({'status': status, 'count': count})
    
    # Logbook data for current month
    current_month = datetime.now().month
    current_year = datetime.now().year
    logbook_entries = fetch_all('logbook')
    logbook_data = []
    date_counts = defaultdict(int)
    
    for entry in logbook_entries:
        if entry.get('date'):
            entry_date = entry['date']
            if isinstance(entry_date, str):
                try:
                    entry_date = datetime.strptime(entry_date, '%Y-%m-%d')
                except:
                    continue
            if entry_date.month == current_month and entry_date.year == current_year:
                date_counts[entry_date.strftime('%Y-%m-%d')] += 1
    
    for log_date, count in sorted(date_counts.items()):
        logbook_data.append({'log_date': log_date, 'count': count})
    
    # Report types count
    reports = fetch_all('reports')
    report_data = []
    type_counts = defaultdict(int)
    for report in reports:
        type_counts[report.get('type', 'Unknown')] += 1
    for rtype, count in type_counts.items():
        report_data.append({'type': rtype, 'count': count})
    
    return project_data, logbook_data, report_data

def get_user_stats(user_id):
    # Get user's projects count
    user_projects = count_rows('projects', {'created_by': user_id})
    
    # Get user's reports count
    user_reports = count_rows('reports', {'created_by': user_id})
    
    # Get user's logbook count
    user_logbook = count_rows('logbook', {'created_by': user_id})
    
    return user_projects, user_reports, user_logbook

# Helper function to get available reports for linking
def get_available_reports(project_id):
    # Get all reports
    all_reports = fetch_all('reports', order_by=('uploaded_at', False))
    
    # Get reports already linked to this project
    linked_reports = fetch_all('project_reports', {'project_id': project_id})
    linked_report_ids = {r['report_id'] for r in linked_reports}
    
    # Filter out already linked reports
    available_reports = [r for r in all_reports if r['id'] not in linked_report_ids]
    return available_reports

# Helper function to get available projects for linking
def get_available_projects():
    return fetch_all('projects', order_by='name')

# Helper function to get projects pending approval
def get_projects_pending_approval():
    """Get projects that are pending SK Chairman approval"""
    return fetch_all('projects', {'approved_by_sk_chairman': False}, order_by=('created_at', False))

# Helper function to get all users
def get_all_users():
    """Get all users for displaying creator names"""
    return fetch_all('users')

# --- Enhanced Dashboard Analytics ---
def get_dashboard_analytics():
    # Get basic counts
    projects_total = count_rows('projects')
    projects_approved = count_rows('projects', {'approved_by_sk_chairman': True})
    projects_ongoing = count_rows('projects', {'status': 'On-going'})
    projects_completed = count_rows('projects', {'status': 'Completed'})
    projects_planned = count_rows('projects', {'status': 'Planned'})
    reports_total = count_rows('reports')
    
    # Get report types count (categorized by type)
    reports = fetch_all('reports')
    report_types_data = []
    type_counts = defaultdict(int)
    
    for report in reports:
        report_type = report.get('type', 'Unknown')
        if report_type:
            type_counts[report_type] += 1
    
    # Convert to list of dictionaries for chart data
    for rtype, count in sorted(type_counts.items()):
        report_types_data.append({
            'type': rtype,
            'count': count
        })
    
    # Reports this month (count)
    current_month = datetime.now().month
    current_year = datetime.now().year
    reports_this_month = 0
    for report in reports:
        uploaded_at = report.get('uploaded_at')
        if uploaded_at:
            uploaded_at_dt = parse_datetime(uploaded_at)
            if uploaded_at_dt and uploaded_at_dt.month == current_month and uploaded_at_dt.year == current_year:
                reports_this_month += 1
    
    # Reports with files (count)
    reports_with_files = 0
    for report in reports:
        if report.get('filename'):
            reports_with_files += 1
    
    reports_approved = projects_approved
    logbook_total = count_rows('logbook')
    
    # Logbook today
    today = date_module.today().strftime('%Y-%m-%d')
    logbook_today = count_rows('logbook', {'date': today})
    
    # Logbook this month - detailed data for chart
    logbook_entries = fetch_all('logbook')
    
    # Get logbook entries for current month (for chart)
    logbook_current_month_data = []
    monthly_log_counts = defaultdict(int)
    
    for entry in logbook_entries:
        entry_date = entry.get('date')
        if entry_date:
            entry_date_dt = parse_datetime(entry_date)
            if entry_date_dt and entry_date_dt.month == current_month and entry_date_dt.year == current_year:
                # Format date as string for grouping
                date_str = entry_date_dt.strftime('%Y-%m-%d')
                monthly_log_counts[date_str] += 1
    
    # Convert to list sorted by date
    for log_date, count in sorted(monthly_log_counts.items()):
        logbook_current_month_data.append({
            'date': log_date,
            'count': count
        })
    
    # Count totals for statistics
    logbook_this_month = 0
    logbook_with_evidence = 0
    for entry in logbook_entries:
        entry_date = entry.get('date')
        if entry_date:
            entry_date_dt = parse_datetime(entry_date)
            if entry_date_dt and entry_date_dt.month == current_month and entry_date_dt.year == current_year:
                logbook_this_month += 1
        
        if entry.get('evidence_files'):
            logbook_with_evidence += 1
    
    # Logbook this week
    week_ago = (datetime.now() - timedelta(days=7)).date()
    logbook_this_week = 0
    for entry in logbook_entries:
        entry_date = entry.get('date')
        if entry_date:
            entry_date_dt = parse_datetime(entry_date)
            if entry_date_dt and entry_date_dt.date() >= week_ago:
                logbook_this_week += 1
    
    users_total = count_rows('users')
    
    # Budget statistics
    budgets_total = count_rows('budgets')
    budgets = fetch_all('budgets')
    total_budget_balance = 0
    total_budget_allocated = 0
    
    for budget in budgets:
        total_budget_balance += float(budget.get('current_balance', 0))
        total_budget_allocated += float(budget.get('total_amount', 0))
    
    # Calculate budget utilization percentage
    if total_budget_allocated > 0:
        budget_used = total_budget_allocated - total_budget_balance
        budget_utilization_percentage = (budget_used / total_budget_allocated) * 100
        budget_remaining_percentage = 100 - budget_utilization_percentage
    else:
        budget_utilization_percentage = 0
        budget_remaining_percentage = 0
        budget_used = 0
    
    pending_approvals = count_rows('budget_entries', {'status': 'pending'})
    
    # Get user roles count
    users = fetch_all('users')
    roles_count = defaultdict(int)
    for user in users:
        role = user.get('role', 'unknown')
        roles_count[role] += 1
    
    # Get user contributions by role
    user_roles = ['SK_Chairman', 'Secretary', 'Treasurer', 'BMO', 'super_admin']
    user_contributions = []
    for role in user_roles:
        count = 0
        for user in users:
            if user.get('role') == role:
                user_id = user['id']
                count += count_rows('projects', {'created_by': user_id})
        user_contributions.append(count)
    
    # Get logbook activity for last 7 days (for dashboard chart)
    logbook_dates = []
    logbook_counts = []
    for i in range(6, -1, -1):
        date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        count = count_rows('logbook', {'date': date_str})
        logbook_dates.append((datetime.now() - timedelta(days=i)).strftime('%m/%d'))
        logbook_counts.append(count)
    
    return {
        'projects_total': projects_total,
        'projects_approved': projects_approved,
        'projects_ongoing': projects_ongoing,
        'projects_completed': projects_completed,
        'projects_planned': projects_planned,
        'reports_total': reports_total,
        'reports_this_month': reports_this_month,
        'reports_with_files': reports_with_files,
        'reports_approved': reports_approved,
        'logbook_total': logbook_total,
        'logbook_today': logbook_today,
        'logbook_this_month': logbook_this_month,
        'logbook_with_evidence': logbook_with_evidence,
        'logbook_this_week': logbook_this_week,
        'users_total': users_total,
        'budgets_total': budgets_total,
        'total_budget_balance': total_budget_balance,
        'total_budget_allocated': total_budget_allocated,
        'budget_used': budget_used,
        'budget_utilization_percentage': budget_utilization_percentage,
        'budget_remaining_percentage': budget_remaining_percentage,
        'pending_approvals': pending_approvals,
        'roles_count': roles_count,
        'report_types_data': report_types_data,  # New: categorized report data
        'logbook_current_month_data': logbook_current_month_data,  # New: monthly logbook data
        'user_roles': user_roles,
        'user_contributions': user_contributions,
        'logbook_dates': logbook_dates,
        'logbook_counts': logbook_counts
    }

def get_recent_activities():
    """Get recent activities for the dashboard including budget activities"""
    activities = []
    
    try:
        # Get recent budget activities (most recent 10)
        recent_budget_activities = fetch_all('budget_activity_history', order_by=('performed_at', False), limit=10)
        
        for activity in recent_budget_activities:
            performed_at = parse_datetime(activity.get('performed_at'))
            if performed_at:
                # Create activity object in the same format as other activities
                activities.append({
                    'type': 'budget',
                    'description': activity.get('description', 'Budget Activity'),
                    'time': performed_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'time_obj': performed_at,
                    'activity_type': activity.get('activity_type', 'budget_activity'),
                    'performer_name': activity.get('performer_name', 'Unknown'),
                    'budget_name': activity.get('budget_name'),
                    'amount_changed': activity.get('amount_changed', 0),
                    'old_balance': activity.get('old_balance'),
                    'new_balance': activity.get('new_balance')
                })
        
        # Recent projects
        recent_projects = fetch_all('projects', order_by=('created_at', False), limit=5)
        for project in recent_projects:
            created_at = parse_datetime(project.get('created_at'))
            activities.append({
                'type': 'project',
                'description': f'Project: {project.get("name", "Unnamed")}',
                'time': created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else 'Recent',
                'time_obj': created_at
            })
        
        # Recent reports
        recent_reports = fetch_all('reports', order_by=('uploaded_at', False), limit=5)
        for report in recent_reports:
            uploaded_at = parse_datetime(report.get('uploaded_at'))
            activities.append({
                'type': 'report',
                'description': f'New report uploaded: {report.get("type", "Unknown")}',
                'time': uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if uploaded_at else 'N/A',
                'time_obj': uploaded_at
            })
        
        # Recent logbook entries
        recent_logbook = fetch_all('logbook', order_by=('date', False), limit=5)
        for entry in recent_logbook:
            entry_date = parse_datetime(entry.get('date'))
            activities.append({
                'type': 'logbook',
                'description': f'New logbook entry: {entry.get("first_name", "")} {entry.get("last_name", "")}',
                'time': entry_date.strftime('%Y-%m-%d') if entry_date else 'N/A',
                'time_obj': entry_date
            })
    
    except Exception as e:
        print(f"Error getting recent activities: {e}")
        activities = [
            {
                'type': 'system',
                'description': 'System initialized',
                'time': datetime.now().strftime('%H:%M'),
                'time_obj': datetime.now()
            }
        ]
    
    # Sort by datetime objects, not strings
    return sorted(activities, key=lambda x: x['time_obj'] if x['time_obj'] else datetime.min, reverse=True)[:15]

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('base/index.html')

# --- LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # DEBUG: Print what we're receiving
        print(f"Login attempt - Username: {username}, Password: {password}")
        
        try:
            # First, query user by username only
            result = supabase.table('users').select('*').eq('username', username).execute()
            
            if result.data and len(result.data) > 0:
                user = result.data[0]
                print(f"Found user: {user['username']}, DB password: {user['password']}")
                
                # Then check password manually
                if user['password'] == password:
                    session['user'] = {
                        'id': user['id'],
                        'username': user['username'],
                        'fullname': user['fullname'],
                        'role': user['role']
                    }
                    flash(f"Welcome, {user['fullname']}", 'success')

                    role = user['role']
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
                else:
                    print("Password mismatch")
                    flash('Invalid credentials', 'danger')
            else:
                print("User not found")
                flash('Invalid credentials', 'danger')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login error occurred', 'danger')
            
    return render_template('base/login.html')

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
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Ensure all chart data is available
    if 'logbook_dates' not in analytics:
        analytics['logbook_dates'] = []
        analytics['logbook_counts'] = []
    
    if 'report_categories' not in analytics:
        analytics['report_categories'] = []
        analytics['report_counts'] = []
    
    return render_template('base/dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         user_logbook=user_logbook,
                         sidebar_open=sidebar_open,
                         **analytics)

# --- SUPER ADMIN ---
@app.route('/superadmin')
@login_required(role='super_admin')
def superadmin_dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    users = fetch_all('users')
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template(
        'base/dashboard_base.html',
        users=users,
        recent_activities=recent_activities,
        user_projects=user_projects,
        user_reports=user_reports,
        user_logbook=user_logbook,
        sidebar_open=sidebar_open,
        **analytics
    )

# --- USER MANAGEMENT (Super Admin Only) ---
@app.route('/user_management')
@login_required(role='super_admin')
def user_management():
    users = fetch_all('users', order_by='id')
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('super_admin/user_management.html', users=users, sidebar_open=sidebar_open)

@app.route('/user_management/add', methods=['GET', 'POST'])
@login_required(role='super_admin')
def add_user():
    sidebar_open = request.args.get('sidebar') == 'open'
    
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        if not fullname or not username or not password or not role:
            flash('All fields are required', 'danger')
            return redirect(url_for('add_user'))

        user_data = {
            'fullname': fullname,
            'username': username,
            'password': password,
            'role': role
        }
        
        insert_data('users', user_data)
        flash('User added successfully!', 'success')
        return redirect(url_for('user_management') + '?sidebar=open')

    return render_template('super_admin/add_user.html', sidebar_open=sidebar_open)

@app.route('/user_management/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required(role='super_admin')
def edit_user_account(user_id):
    sidebar_open = request.args.get('sidebar') == 'open'
    
    user = fetch_one('users', {'id': user_id})

    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('user_management'))

    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        if not fullname or not username or not role:
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('edit_user_account', user_id=user_id))

        update_dict = {
            'fullname': fullname,
            'username': username,
            'role': role
        }
        
        if password:
            update_dict['password'] = password
        
        update_data('users', user_id, update_dict)
        flash('User updated successfully!', 'success')
        return redirect(url_for('user_management') + '?sidebar=open')

    return render_template('super_admin/edit_user.html', user=user, sidebar_open=sidebar_open)

@app.route('/user_management/delete/<int:user_id>')
@login_required(role='super_admin')
def delete_user(user_id):
    delete_data('users', user_id)
    flash('User deleted successfully!', 'info')
    return redirect(url_for('user_management') + '?sidebar=open')

# --- PROJECT APPROVALS PAGE ---
@app.route('/project_approvals')
@login_required(role='SK_Chairman')
def project_approvals():
    """Page for SK Chairman to approve multiple projects at once"""
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Get all projects for statistics
    all_projects = fetch_all('projects')
    
    # Calculate statistics
    total_projects = len(all_projects)
    planned_count = sum(1 for p in all_projects if p.get('status', '').lower() == 'planned')
    ongoing_count = sum(1 for p in all_projects if p.get('status', '').lower() in ['on-going', 'ongoing'])
    completed_count = sum(1 for p in all_projects if p.get('status', '').lower() == 'completed')
    
    # Get projects pending approval
    pending_projects = get_projects_pending_approval()
    
    # Get approved projects for reference (last 10)
    approved_projects = fetch_all('projects', {'approved_by_sk_chairman': True}, 
                                 order_by=('approved_at', False), limit=10)
    
    # Get all users for displaying creator names
    users = get_all_users()
    
    # Parse datetime for approved projects
    for project in approved_projects:
        if project.get('approved_at'):
            approved_at_dt = parse_datetime(project.get('approved_at'))
            project['approved_at_dt'] = approved_at_dt
        else:
            project['approved_at_dt'] = None
        
        # Also get who approved it
        if project.get('approved_by'):
            approver = fetch_one('users', {'id': project['approved_by']})
            if approver:
                project['approved_by_name'] = approver.get('fullname')
    
    return render_template('projects/project_approvals.html',
                         pending_projects=pending_projects,
                         approved_projects=approved_projects,
                         users=users,
                         total_projects=total_projects,
                         planned_count=planned_count,
                         ongoing_count=ongoing_count,
                         completed_count=completed_count,
                         sidebar_open=sidebar_open)

@app.route('/projects/batch_approve', methods=['POST'])
@login_required(role='SK_Chairman')
def batch_approve_projects():
    """Approve multiple projects at once"""
    project_ids = request.form.getlist('project_ids')
    
    if not project_ids:
        flash('Please select at least one project to approve', 'warning')
        return redirect(url_for('project_approvals') + '?sidebar=open')
    
    approved_count = 0
    for project_id in project_ids:
        try:
            project_id = int(project_id)
            project = fetch_one('projects', {'id': project_id})
            
            if project and not project.get('approved_by_sk_chairman', False):
                approved_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                
                update_data('projects', project_id, {
                    'approved_by_sk_chairman': True,
                    'approved_at': approved_at,
                    'approved_by': session['user']['id']
                })
                
                approved_count += 1
        except (ValueError, TypeError) as e:
            print(f"Error processing project ID {project_id}: {e}")
            continue
    
    flash(f'Successfully approved {approved_count} project(s)!', 'success')
    return redirect(url_for('project_approvals') + '?sidebar=open')

@app.route('/projects/<int:proj_id>/quick_approve', methods=['POST'])
@login_required(role='SK_Chairman')
def quick_approve_project(proj_id):
    """Quick approve a single project from approvals page"""
    project = fetch_one('projects', {'id': proj_id})
    
    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('project_approvals'))
    
    if project.get('approved_by_sk_chairman', False):
        flash('Project is already approved', 'info')
        return redirect(url_for('project_approvals') + '?sidebar=open')
    
    approved_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    update_data('projects', proj_id, {
        'approved_by_sk_chairman': True,
        'approved_at': approved_at,
        'approved_by': session['user']['id']
    })
    
    flash(f'Project "{project.get("name", "Unnamed")}" approved successfully!', 'success')
    return redirect(url_for('project_approvals') + '?sidebar=open')

# --- PROJECTS (with pagination) ---
@app.route('/projects')
@login_required()
def projects():
    page = request.args.get('page', 1, type=int)
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Get all projects for statistics
    all_projects = fetch_all('projects')
    
    # Calculate statistics
    total_projects = len(all_projects)
    planned_projects = sum(1 for p in all_projects if p.get('status', '').lower() == 'planned')
    ongoing_projects = sum(1 for p in all_projects if p.get('status', '').lower() in ['on-going', 'ongoing'])
    completed_projects = sum(1 for p in all_projects if p.get('status', '').lower() == 'completed')
    
    # Calculate approval statistics
    pending_approval_projects = sum(1 for p in all_projects if not p.get('approved_by_sk_chairman', False))
    approved_projects_count = sum(1 for p in all_projects if p.get('approved_by_sk_chairman', False))
    
    # Get total count for pagination
    total_items = count_rows('projects')
    print(f"DEBUG projects(): Total projects in DB: {total_items}")
    
    # Calculate pagination
    pagination = get_pagination_data(page, total_items)
    
    # Get paginated projects
    try:
        projects_data = fetch_all('projects', 
                                order_by=('created_at', False), 
                                limit=pagination['per_page'], 
                                offset=pagination['offset'])
        
        print(f"DEBUG projects(): Retrieved {len(projects_data)} projects for page {page}")
        
    except Exception as e:
        print(f"Error fetching projects: {e}")
        projects_data = []
    
    # Get budget allocations for each project
    for project in projects_data:
        allocations = fetch_all('project_budgets', {'project_id': project['id']})
        if allocations:
            allocation = allocations[0]
            project['allocated_budget'] = allocation.get('allocated_amount', 0)
            # Get budget name
            budget = fetch_one('budgets', {'id': allocation.get('budget_id')})
            project['budget_name'] = budget.get('name') if budget else None
        else:
            project['allocated_budget'] = 0
            project['budget_name'] = None
        
        # Ensure approved_by_sk_chairman field exists and is properly typed
        if 'approved_by_sk_chairman' not in project:
            project['approved_by_sk_chairman'] = False
        elif isinstance(project['approved_by_sk_chairman'], str):
            # Convert string to boolean if needed
            project['approved_by_sk_chairman'] = project['approved_by_sk_chairman'].lower() in ['true', '1', 'yes', 't']
        
        # Get linked reports for each project
        project_reports = fetch_all('project_reports', {'project_id': project['id']})
        linked_reports = []
        for pr in project_reports:
            report = fetch_one('reports', {'id': pr['report_id']})
            if report:
                # Parse uploaded_at into datetime object for display
                uploaded_at_dt = parse_datetime(report.get('uploaded_at'))
                if uploaded_at_dt:
                    report['uploaded_at_dt'] = uploaded_at_dt
                else:
                    report['uploaded_at_dt'] = datetime.now()
                linked_reports.append(report)
        project['linked_reports'] = linked_reports
    
    return render_template('projects/projects.html', 
                         projects=projects_data, 
                         sidebar_open=sidebar_open,
                         pagination=pagination,
                         total_projects=total_projects,
                         planned_projects=planned_projects,
                         ongoing_projects=ongoing_projects,
                         completed_projects=completed_projects,
                         pending_approval_projects=pending_approval_projects,
                         approved_projects_count=approved_projects_count,
                         min=min)

@app.route('/projects/new', methods=['GET', 'POST'])
@login_required()
def project_new():
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

        project_data = {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'details': details,
            'status': status,
            'filename': filename_db,
            'created_by': session['user']['id'],
            'created_at': datetime.now().isoformat()
        }
        
        print(f"DEBUG project_new(): Creating project with data: {project_data}")
        
        result = insert_data('projects', project_data)
        
        if result:
            print(f"DEBUG project_new(): Project created with ID: {result.get('id')}")
            flash('Project added successfully!', 'success')
            return redirect(url_for('projects') + '?sidebar=open')
        else:
            flash('Failed to create project', 'danger')
            return redirect(url_for('project_new'))
    
    return render_template('projects/project_new.html', sidebar_open=sidebar_open)

@app.route('/projects/delete/<int:proj_id>')
@login_required()
def project_delete(proj_id):
    project = fetch_one('projects', {'id': proj_id})

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    # Delete associated project reports
    project_reports = fetch_all('project_reports', {'project_id': proj_id})
    for pr in project_reports:
        delete_data('project_reports', pr['id'])
    
    # Delete project budgets
    project_budgets = fetch_all('project_budgets', {'project_id': proj_id})
    for pb in project_budgets:
        delete_data('project_budgets', pb['id'])
    
    # Delete project updates
    project_updates = fetch_all('project_updates', {'project_id': proj_id})
    for update in project_updates:
        delete_data('project_updates', update['id'])
    
    # Delete the project
    delete_data('projects', proj_id)

    if project.get('filename'):
        file_path = os.path.join(app.static_folder, project['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: could not delete file {file_path}: {e}")

    flash('Project deleted successfully!', 'info')
    return redirect(url_for('projects') + '?sidebar=open')

# --- PROJECT UPDATES & MANAGEMENT ---
@app.route('/projects/<int:proj_id>/updates', methods=['GET', 'POST'])
@login_required()
def project_updates(proj_id):
    if request.method == 'POST':
        # Check if this is a project update addition
        if 'add_update' in request.form:
            update_content = request.form.get('update_content', '').strip()
            update_date = request.form.get('update_date') or datetime.now().date()
            
            if not update_content:
                flash('Update content is required', 'danger')
                return redirect(url_for('project_updates', proj_id=proj_id))
            
            update_dict = {
                'project_id': proj_id,
                'update_text': update_content,
                'update_date': update_date,
                'created_by': session['user']['id']
            }
            
            insert_data('project_updates', update_dict)
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

            update_dict = {
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'details': details,
                'status': status
            }

            if file and file.filename:
                if allowed_file(file.filename):
                    safe = secure_filename(file.filename)
                    dest = os.path.join(PROJECT_UPLOADS, safe)
                    file.save(dest)
                    filename_db = f'uploads/projects/{safe}'
                    update_dict['filename'] = filename_db
                else:
                    flash('File type not allowed', 'danger')
                    return redirect(url_for('project_updates', proj_id=proj_id))

            update_data('projects', proj_id, update_dict)
            flash('Project updated successfully!', 'success')
        
        return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')
    
    # GET request - show project updates page
    project = fetch_one('projects', {'id': proj_id})
    
    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))
    
    # Get project updates
    updates = fetch_all('project_updates', {'project_id': proj_id}, order_by=('update_date', False))
    
    # Get associated reports
    project_reports = fetch_all('project_reports', {'project_id': proj_id})
    reports = []
    for pr in project_reports:
        report = fetch_one('reports', {'id': pr['report_id']})
        if report:
            reports.append(report)
    
    # Get available reports for linking
    available_reports = get_available_reports(proj_id)
    
    sidebar_open = request.args.get('sidebar') == 'open'
    return render_template('projects/project_updates.html', 
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
    # Get the update
    update = fetch_one('project_updates', {'id': update_id, 'project_id': proj_id})
    
    if not update:
        flash('Update not found', 'danger')
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    # Check if user owns this update or is admin/SK Chairman
    if update['created_by'] != session['user']['id'] and session['user']['role'] not in ['super_admin', 'SK_Chairman']:
        flash('You can only edit your own updates', 'danger')
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    if request.method == 'POST':
        update_content = request.form.get('update_content', '').strip()
        update_date = request.form.get('update_date') or datetime.now().date()
        
        if not update_content:
            flash('Update content is required', 'danger')
            return redirect(url_for('edit_project_update', proj_id=proj_id, update_id=update_id))
        
        update_dict = {
            'update_text': update_content,
            'update_date': update_date,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        update_data('project_updates', update_id, update_dict)
        flash('Project update edited successfully!', 'success')
        return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')
    
    sidebar_open = request.args.get('sidebar') == 'open'
    return render_template('projects/project_edit.html', 
                         project_id=proj_id,
                         update=update,
                         now=datetime.now(),
                         sidebar_open=sidebar_open)

# Delete project update
@app.route('/projects/<int:proj_id>/updates/<int:update_id>/delete')
@login_required()
def delete_project_update(proj_id, update_id):
    # Get the update
    update = fetch_one('project_updates', {'id': update_id, 'project_id': proj_id})
    
    if not update:
        flash('Update not found', 'danger')
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    # Check if user owns this update or is admin/SK Chairman
    if update['created_by'] != session['user']['id'] and session['user']['role'] not in ['super_admin', 'SK_Chairman']:
        flash('You can only delete your own updates', 'danger')
        return redirect(url_for('project_updates', proj_id=proj_id))
    
    delete_data('project_updates', update_id)
    
    flash('Project update deleted successfully!', 'info')
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

# This route is kept for backward compatibility but moved to approvals page
@app.route('/projects/<int:proj_id>/toggle_approval', methods=['POST'])
@login_required(role='SK_Chairman')
def toggle_project_approval(proj_id):
    project = fetch_one('projects', {'id': proj_id})
    
    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))
    
    new_status = not project.get('approved_by_sk_chairman', False)
    approved_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') if new_status else None
    
    update_data('projects', proj_id, {
        'approved_by_sk_chairman': new_status,
        'approved_at': approved_at
    })
    
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
    
    # Check if link already exists
    existing = fetch_one('project_reports', {'project_id': proj_id, 'report_id': report_id})
    
    if not existing:
        link_data = {
            'project_id': proj_id,
            'report_id': report_id
        }
        insert_data('project_reports', link_data)
        flash('Report linked to project successfully!', 'success')
    else:
        flash('This report is already linked to the project', 'info')
    
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

@app.route('/projects/<int:proj_id>/unlink_report/<int:report_id>')
@login_required()
def unlink_report_from_project(proj_id, report_id):
    # Find and delete the link
    links = fetch_all('project_reports', {'project_id': proj_id, 'report_id': report_id})
    for link in links:
        delete_data('project_reports', link['id'])
    
    flash('Report unlinked from project successfully!', 'info')
    return redirect(url_for('project_updates', proj_id=proj_id) + '?sidebar=open')

# --- LOGBOOK (with pagination) ---
@app.route('/logbook', methods=['GET', 'POST'])
@login_required()
def logbook():
    page = request.args.get('page', 1, type=int)
    sidebar_open = request.args.get('sidebar') == 'open'
    
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        middle = request.form.get('middle_name', '').strip()
        last = request.form.get('last_name', '').strip()
        sitio = request.form.get('sitio', '').strip()
        time_in = request.form.get('time_in') or None
        time_out = request.form.get('time_out') or None
        entry_date = request.form.get('date') or None
        concern = request.form.get('concern', '').strip()
        evidence_files = request.files.getlist('evidence')

        if not first or not last or not entry_date:
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

            logbook_data = {
                'first_name': first,
                'middle_name': middle,
                'last_name': last,
                'sitio': sitio,
                'time_in': time_in,
                'time_out': time_out,
                'date': entry_date,
                'concern': concern,
                'evidence_files': evidence_db,
                'created_by': session['user']['id']
            }
            
            print(f"DEBUG logbook(): Creating logbook entry: {logbook_data}")
            
            insert_data('logbook', logbook_data)
            flash('Logbook entry added successfully!', 'success')
            return redirect(url_for('logbook', page=1) + '?sidebar=open')

    # Get total count
    total_items = count_rows('logbook')
    print(f"DEBUG logbook(): Total entries in DB: {total_items}")
    
    # Calculate pagination
    pagination = get_pagination_data(page, total_items)
    
    # Get paginated entries
    entries = fetch_all('logbook', order_by=('date', False), 
                       limit=pagination['per_page'], offset=pagination['offset'])
    
    print(f"DEBUG logbook(): Retrieved {len(entries)} entries for page {page}")
    
    # Get ALL logbook entries for statistics (not just paginated ones)
    all_entries = fetch_all('logbook')
    
    # Calculate statistics
    today_str = date_module.today().strftime('%Y-%m-%d')
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    today_count = 0
    current_month_count = 0
    with_evidence_count = 0
    
    for entry in all_entries:
        entry_date = entry.get('date')
        
        # Count today's entries
        if entry_date == today_str:
            today_count += 1
        
        # Count current month entries
        if entry_date:
            entry_date_dt = parse_datetime(entry_date)
            if entry_date_dt and entry_date_dt.month == current_month and entry_date_dt.year == current_year:
                current_month_count += 1
        
        # Count entries with evidence
        if entry.get('evidence_files'):
            with_evidence_count += 1
    
    print(f"DEBUG logbook(): Statistics - Today: {today_count}, This Month: {current_month_count}, With Evidence: {with_evidence_count}")
    
    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    
    return render_template('logbook/logbook.html', 
                         entries=entries, 
                         sitios=sitios, 
                         sidebar_open=sidebar_open,
                         pagination=pagination,
                         today_count=today_count,
                         current_month_count=current_month_count,
                         with_evidence_count=with_evidence_count,
                         today=date_module.today(),
                         min=min)

@app.route('/logbook/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required()
def logbook_edit(entry_id):
    sidebar_open = request.args.get('sidebar') == 'open'
    
    entry = fetch_one('logbook', {'id': entry_id})
    
    if not entry:
        flash('Logbook entry not found', 'danger')
        return redirect(url_for('logbook'))

    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        middle = request.form.get('middle_name', '').strip()
        last = request.form.get('last_name', '').strip()
        sitio = request.form.get('sitio', '').strip()
        time_in = request.form.get('time_in') or None
        time_out = request.form.get('time_out') or None
        entry_date = request.form.get('date') or None
        concern = request.form.get('concern', '').strip()
        evidence_files = request.files.getlist('evidence')

        if not first or not last or not entry_date:
            flash('Please fill First Name, Last Name and Date', 'danger')
        else:
            update_dict = {
                'first_name': first,
                'middle_name': middle,
                'last_name': last,
                'sitio': sitio,
                'time_in': time_in,
                'time_out': time_out,
                'date': entry_date,
                'concern': concern
            }

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
                update_dict['evidence_files'] = evidence_db

            update_data('logbook', entry_id, update_dict)
            flash('Logbook entry updated successfully!', 'success')
            return redirect(url_for('logbook') + '?sidebar=open')

    sitios = ['Asana 1', 'Asana 2', 'Dao', 'Ipil', 'Maulawin', 'Kamagong', 'Yakal']
    return render_template('logbook/logbook_edit.html', entry=entry, sitios=sitios, sidebar_open=sidebar_open)

@app.route('/logbook/delete/<int:entry_id>')
@login_required()
def logbook_delete(entry_id):
    entry = fetch_one('logbook', {'id': entry_id})
    
    # Delete associated evidence files
    if entry and entry.get('evidence_files'):
        evidence_files = entry['evidence_files'].split(',')
        for filename in evidence_files:
            file_path = os.path.join(LOGBOOK_EVIDENCE_UPLOADS, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Warning: could not delete evidence file {file_path}: {e}")

    delete_data('logbook', entry_id)
    flash('Logbook entry deleted successfully!', 'info')
    return redirect(url_for('logbook') + '?sidebar=open')

@app.route('/logbook/evidence/<int:entry_id>')
@login_required()
def get_logbook_evidence(entry_id):
    entry = fetch_one('logbook', {'id': entry_id})
    
    if entry and entry.get('evidence_files'):
        files = entry['evidence_files'].split(',')
        return {'evidence_files': files}
    return {'evidence_files': []}

@app.route('/uploads/logbook_evidence/<filename>')
def serve_logbook_evidence(filename):
    """Serve logbook evidence files from the correct directory"""
    return send_from_directory(LOGBOOK_EVIDENCE_UPLOADS, filename, as_attachment=False)

# --- REPORTS (with pagination) ---
@app.route('/reports')
@login_required()
def reports():
    page = request.args.get('page', 1, type=int)
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Get total count
    total_items = count_rows('reports')
    print(f"DEBUG reports(): Total reports in DB: {total_items}")
    
    # Calculate pagination
    pagination = get_pagination_data(page, total_items)
    
    # Get paginated reports
    reports_data = fetch_all('reports', order_by=('uploaded_at', False),
                           limit=pagination['per_page'], offset=pagination['offset'])
    
    print(f"DEBUG reports(): Retrieved {len(reports_data)} reports for page {page}")
    
    # Parse datetime strings for template usage AND ensure uploaded_at is a datetime object
    for report in reports_data:
        # Parse uploaded_at into a datetime object
        uploaded_at_dt = parse_datetime(report.get('uploaded_at'))
        
        # Store the datetime object in a new field for template use
        if uploaded_at_dt:
            report['uploaded_at_dt'] = uploaded_at_dt
        else:
            # If parsing fails, use current datetime as fallback
            report['uploaded_at_dt'] = datetime.now()
        
        # Get linked projects for this report
        project_links = fetch_all('project_reports', {'report_id': report['id']})
        linked_projects = []
        for link in project_links:
            project = fetch_one('projects', {'id': link['project_id']})
            if project:
                linked_projects.append(project)
        report['linked_projects'] = linked_projects
    
    # No need for separate list - use reports_data directly
    reports_with_projects = reports_data
    
    return render_template('reports/reports.html', 
                         reports=reports_with_projects, 
                         sidebar_open=sidebar_open,
                         pagination=pagination,
                         min=min)

@app.route('/reports/new', methods=['GET', 'POST'])
@login_required()
def report_new():
    # Restrict access for Treasurer and BMO - VIEW ONLY
    if session['user']['role'] in ['Treasurer', 'BMO']:
        flash('Access denied: Treasurer and BMO can only view reports, not create them', 'danger')
        return redirect(url_for('reports'))
    
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
        
        report_data = {
            'type': rtype,
            'filename': filename_db,
            'uploaded_at': uploaded_at,
            'reported_for': reported_for,
            'notes': notes,
            'created_by': session['user']['id']
        }
        
        print(f"DEBUG report_new(): Creating report with data: {report_data}")
        
        result = insert_data('reports', report_data)
        
        # Link to project if selected
        if project_id and project_id != '' and result:
            link_data = {
                'project_id': project_id,
                'report_id': result['id']
            }
            insert_data('project_reports', link_data)
        
        flash('Report registered successfully!', 'success')
        return redirect(url_for('reports') + '?sidebar=open')

    available_projects = get_available_projects()
    return render_template('reports/report_new.html', sidebar_open=sidebar_open, available_projects=available_projects)

@app.route('/reports/edit/<int:rep_id>', methods=['GET', 'POST'])
@login_required()
def report_edit(rep_id):
    # Restrict access for Treasurer and BMO - VIEW ONLY
    if session['user']['role'] in ['Treasurer', 'BMO']:
        flash('Access denied: Treasurer and BMO can only view reports, not edit them', 'danger')
        return redirect(url_for('reports'))
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    report = fetch_one('reports', {'id': rep_id})

    if not report:
        flash('Report not found', 'danger')
        return redirect(url_for('reports'))

    # Get linked projects
    project_links = fetch_all('project_reports', {'report_id': rep_id})
    linked_projects = []
    for link in project_links:
        project = fetch_one('projects', {'id': link['project_id']})
        if project:
            linked_projects.append(project)

    if request.method == 'POST':
        rtype = request.form.get('type', '').strip()
        reported_for = request.form.get('reported_for', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')
        project_id = request.form.get('project_id')

        update_dict = {
            'type': rtype,
            'reported_for': reported_for,
            'notes': notes
        }

        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(REPORT_UPLOADS, safe)
                file.save(dest)
                update_dict['filename'] = f'uploads/reports/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('report_edit', rep_id=rep_id))

        update_data('reports', rep_id, update_dict)
        
        # Link to new project if selected
        if project_id and project_id != '':
            # Check if link already exists
            existing = fetch_one('project_reports', {'project_id': project_id, 'report_id': rep_id})
            if not existing:
                link_data = {
                    'project_id': project_id,
                    'report_id': rep_id
                }
                insert_data('project_reports', link_data)
        
        flash('Report updated successfully!', 'success')
        return redirect(url_for('reports') + '?sidebar=open')

    available_projects = get_available_projects()
    return render_template('reports/report_edit.html', report=report, sidebar_open=sidebar_open, 
                         available_projects=available_projects, linked_projects=linked_projects)

@app.route('/reports/delete/<int:rep_id>')
@login_required()
def report_delete(rep_id):
    report = fetch_one('reports', {'id': rep_id})

    if not report:
        flash('Report not found', 'danger')
        return redirect(url_for('reports'))

    # Delete project report links
    project_links = fetch_all('project_reports', {'report_id': rep_id})
    for link in project_links:
        delete_data('project_reports', link['id'])
    
    # Delete the report
    delete_data('reports', rep_id)

    if report.get('filename'):
        file_path = os.path.join(app.static_folder, report['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: could not delete file {file_path}: {e}")

    flash('Report deleted successfully!', 'info')
    return redirect(url_for('reports') + '?sidebar=open')

# --- DASHBOARDS WITH CHARTS ---
@app.route('/chairman')
@login_required(role='SK_Chairman')
def sk_chairman_dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('base/dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         user_logbook=user_logbook,
                         sidebar_open=sidebar_open,
                         **analytics)

@app.route('/secretary')
@login_required(role='Secretary')
def secretary_dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('base/dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         user_logbook=user_logbook,
                         sidebar_open=sidebar_open,
                         **analytics)

@app.route('/treasurer')
@login_required(role='Treasurer')
def treasurer_dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('base/dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         user_logbook=user_logbook,
                         sidebar_open=sidebar_open,
                         **analytics)

@app.route('/bmo')
@login_required(role='BMO')
def bmo_dashboard():
    analytics = get_dashboard_analytics()
    recent_activities = get_recent_activities()
    user_projects, user_reports, user_logbook = get_user_stats(session['user']['id'])
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    return render_template('base/dashboard_base.html',
                         recent_activities=recent_activities,
                         user_projects=user_projects,
                         user_reports=user_reports,
                         user_logbook=user_logbook,
                         sidebar_open=sidebar_open,
                         **analytics)

# ====== BUDGET MANAGEMENT ROUTES ======

@app.route('/budget_approvals')
@login_required()
def budget_approvals():
    """Page to view and manage budget approvals"""
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Get all budget entries with their status
    all_entries = fetch_all('budget_entries', order_by=('entry_date', False))
    
    # Enhance entries with additional data and parse datetime
    for entry in all_entries:
        if entry.get('budget_id'):
            budget = fetch_one('budgets', {'id': entry['budget_id']})
            entry['budget_name'] = budget.get('name') if budget else None
        
        if entry.get('created_by'):
            creator = fetch_one('users', {'id': entry['created_by']})
            entry['creator_name'] = creator.get('fullname') if creator else None
        
        if entry.get('approved_by'):
            approver = fetch_one('users', {'id': entry['approved_by']})
            entry['approver_name'] = approver.get('fullname') if approver else None
        
        if entry.get('project_id'):
            project = fetch_one('projects', {'id': entry['project_id']})
            entry['project_name'] = project.get('name') if project else None
        
        # Parse datetime fields
        entry['entry_date_dt'] = parse_datetime(entry.get('entry_date'))
        entry['approved_at_dt'] = parse_datetime(entry.get('approved_at'))
    
    # Get pending project allocations
    pending_allocations = fetch_all('project_budgets', {'status': 'pending'}, order_by=('created_at', False))
    
    # Enhance allocations with additional data
    for allocation in pending_allocations:
        if allocation.get('budget_id'):
            budget = fetch_one('budgets', {'id': allocation['budget_id']})
            allocation['budget_name'] = budget.get('name') if budget else None
        
        if allocation.get('project_id'):
            project = fetch_one('projects', {'id': allocation['project_id']})
            allocation['project_name'] = project.get('name') if project else None
            allocation['project_status'] = project.get('status') if project else None
        
        if allocation.get('created_by'):
            creator = fetch_one('users', {'id': allocation['created_by']})
            allocation['creator_name'] = creator.get('fullname') if creator else None
        
        # Parse datetime fields
        allocation['created_at_dt'] = parse_datetime(allocation.get('created_at'))
        allocation['approved_at_dt'] = parse_datetime(allocation.get('approved_at'))
    
    # Group entries by status
    pending_entries = [e for e in all_entries if e.get('status') == 'pending']
    approved_entries = [e for e in all_entries if e.get('status') == 'approved']
    rejected_entries = [e for e in all_entries if e.get('status') == 'rejected']
    
    return render_template('budgets/budget_approvals.html',
                         pending_entries=pending_entries,
                         approved_entries=approved_entries,
                         rejected_entries=rejected_entries,
                         pending_allocations=pending_allocations,
                         sidebar_open=sidebar_open)

# --- BUDGETS (with pagination) ---
@app.route('/budgets')
@login_required()
def budgets():
    page = request.args.get('page', 1, type=int)
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Restrict access for Treasurer, BMO, and Secretary to view only
    if session['user']['role'] in ['Secretary']:
        is_view_only = True
    elif session['user']['role'] in ['Treasurer', 'BMO']:
        is_view_only = False
    else:
        is_view_only = False
    
    # Get total count
    total_items = count_rows('budgets')
    print(f"DEBUG budgets(): Total budgets in DB: {total_items}")
    
    # Calculate pagination
    pagination = get_pagination_data(page, total_items)
    
    # Get paginated budgets
    budgets_data = fetch_all('budgets', order_by=('created_at', False),
                           limit=pagination['per_page'], offset=pagination['offset'])
    
    print(f"DEBUG budgets(): Retrieved {len(budgets_data)} budgets for page {page}")
    
    # Parse datetime fields for templates
    for budget in budgets_data:
        created_at_dt = parse_datetime(budget.get('created_at'))
        if created_at_dt:
            budget['created_at_dt'] = created_at_dt
        else:
            budget['created_at_dt'] = datetime.now()
    
    # Get budget statistics and linked projects
    for budget in budgets_data:
        # Get budget entries for this budget
        entries = fetch_all('budget_entries', {'budget_id': budget['id']})
        
        total_income = 0
        total_expenses = 0
        pending_count = 0
        
        for entry in entries:
            if entry.get('status') == 'approved':
                if entry.get('entry_type') == 'increase':
                    total_income += float(entry.get('amount', 0))
                elif entry.get('entry_type') == 'decrease':
                    total_expenses += float(entry.get('amount', 0))
            elif entry.get('status') == 'pending':
                pending_count += 1
        
        budget['total_income'] = total_income
        budget['total_expenses'] = total_expenses
        budget['pending_approvals'] = pending_count
        
        # Get linked projects
        project_allocations = fetch_all('project_budgets', {'budget_id': budget['id']})
        linked_projects = []
        for allocation in project_allocations:
            if allocation.get('project_id'):
                project = fetch_one('projects', {'id': allocation['project_id']})
                if project:
                    linked_projects.append(project)
        budget['linked_projects'] = linked_projects
    
    # Get recent activity
    recent_activity = fetch_all('budget_activity_history', order_by=('performed_at', False), limit=10)
    
    # Parse datetime for recent activity
    for activity in recent_activity:
        performed_at_dt = parse_datetime(activity.get('performed_at'))
        if performed_at_dt:
            activity['performed_at_dt'] = performed_at_dt
        else:
            activity['performed_at_dt'] = datetime.now()
    
    return render_template('budgets/budgets.html', 
                         budgets=budgets_data, 
                         recent_activity=recent_activity,
                         is_view_only=is_view_only,
                         sidebar_open=sidebar_open,
                         pagination=pagination,
                         min=min)

@app.route('/budgets/new', methods=['GET', 'POST'])
@login_required()
def new_budget():
    # Restrict access: Only SK_Chairman, Treasurer, BMO, and super_admin can create budgets
    if session['user']['role'] not in ['SK_Chairman', 'Treasurer', 'BMO', 'super_admin']:
        flash('Access denied: Only SK Chairman, Treasurer, BMO, and Super Admin can create budgets', 'danger')
        return redirect(url_for('budgets'))
    
    sidebar_open = request.args.get('sidebar') == 'open'
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        initial_amount = request.form.get('initial_amount', '0').strip()
        
        if not name:
            flash('Budget name is required', 'danger')
            return redirect(url_for('new_budget'))
        
        try:
            initial_amount = Decimal(initial_amount)
        except:
            initial_amount = Decimal('0')
        
        budget_data = {
            'name': name,
            'total_amount': float(initial_amount),
            'current_balance': float(initial_amount),
            'created_by': session['user']['id']
        }
        
        print(f"DEBUG new_budget(): Creating budget with data: {budget_data}")
        
        result = insert_data('budgets', budget_data)
        
        # Log budget creation activity
        if result:
            log_budget_activity(
                budget_id=result['id'],
                description=f"Budget '{name}' created with initial amount of ₱{initial_amount:,.2f}",
                performer_id=session['user']['id'],
                amount_changed=initial_amount,
                entry_type='budget_created'
            )
        
        # If there's initial amount, create an entry with proper approval status
        if initial_amount > 0 and result:
            # Determine approval status based on user role
            if session['user']['role'] in ['SK_Chairman', 'super_admin']:
                status = 'approved'
                approved_by = session['user']['id']
                approved_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            else:
                status = 'pending'
                approved_by = None
                approved_at = None
            
            entry_data = {
                'budget_id': result['id'],
                'entry_type': 'increase',
                'amount': float(initial_amount),
                'description': 'Initial budget allocation',
                'entry_date': datetime.now().date().strftime('%Y-%m-%d'),
                'status': status,
                'approved_by': approved_by,
                'approved_at': approved_at,
                'created_by': session['user']['id']
            }
            
            entry_result = insert_data('budget_entries', entry_data)
            
            # Log entry creation activity
            if entry_result:
                log_budget_entry_activity(entry_result['id'], 'create', session['user']['id'])
        
        flash(f'Budget "{name}" created successfully!', 'success')
        return redirect(url_for('budgets') + '?sidebar=open')
    
    return render_template('budgets/new_budget_entry.html', sidebar_open=sidebar_open)

@app.route('/budgets/<int:budget_id>/entries/new', methods=['GET', 'POST'])
@login_required()
def new_budget_entry(budget_id):
    sidebar_open = request.args.get('sidebar') == 'open'
    
    budget = fetch_one('budgets', {'id': budget_id})
    
    if not budget:
        flash('Budget not found', 'danger')
        return redirect(url_for('budgets'))
    
    if request.method == 'POST':
        entry_type = request.form.get('entry_type', '').strip()
        amount = request.form.get('amount', '0').strip()
        description = request.form.get('description', '').strip()
        entry_date = request.form.get('entry_date', '') or datetime.now().date()
        evidence_file = request.files.get('evidence')
        project_id = request.form.get('project_id') or None
        
        if not entry_type or not amount or not description:
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('new_budget_entry', budget_id=budget_id))
        
        try:
            amount = Decimal(amount)
        except:
            flash('Invalid amount', 'danger')
            return redirect(url_for('new_budget_entry', budget_id=budget_id))
        
        # Check if user needs approval
        if session['user']['role'] in ['SK_Chairman', 'super_admin']:
            status = 'approved'
            approved_by = session['user']['id']
            approved_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        else:
            status = 'pending'
            approved_by = None
            approved_at = None
        
        # Handle evidence file
        evidence_filename = None
        if evidence_file and evidence_file.filename:
            if allowed_file(evidence_file.filename):
                safe = secure_filename(evidence_file.filename)
                dest = os.path.join(BUDGET_EVIDENCE_UPLOADS, safe)
                evidence_file.save(dest)
                evidence_filename = f'uploads/budget_evidence/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('new_budget_entry', budget_id=budget_id))
        
        # Create the entry
        entry_data = {
            'budget_id': budget_id,
            'entry_type': entry_type,
            'amount': float(amount),
            'description': description,
            'entry_date': entry_date,
            'status': status,
            'approved_by': approved_by,
            'approved_at': approved_at,
            'evidence_filename': evidence_filename,
            'created_by': session['user']['id'],
            'project_id': project_id
        }
        
        print(f"DEBUG new_budget_entry(): Creating budget entry: {entry_data}")
        
        result = insert_data('budget_entries', entry_data)
        
        # Log entry creation activity
        if result:
            log_budget_entry_activity(result['id'], 'create', session['user']['id'])
        
        flash(f'Budget entry created successfully! Status: {status}', 'success')
        return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')
    
    # Get available projects for linking
    projects = fetch_all('projects', order_by='name')
    
    return render_template('budgets/new_budget_entry.html', 
                         budget=budget, 
                         projects=projects,
                         datetime=datetime,
                         sidebar_open=sidebar_open)

# --- BUDGET DETAILS (with pagination for entries) ---
@app.route('/budgets/<int:budget_id>')
@login_required()
def budget_details(budget_id):
    page = request.args.get('page', 1, type=int)
    sidebar_open = request.args.get('sidebar') == 'open'
    
    # Get budget details
    budget = fetch_one('budgets', {'id': budget_id})
    
    if not budget:
        flash('Budget not found', 'danger')
        return redirect(url_for('budgets'))
    
    # Parse datetime for budget
    budget['created_at_dt'] = parse_datetime(budget.get('created_at'))
    
    # Get total count of entries
    total_items = count_rows('budget_entries', {'budget_id': budget_id})
    
    # Calculate pagination
    pagination = get_pagination_data(page, total_items)
    
    # Get paginated budget entries
    entries = fetch_all('budget_entries', {'budget_id': budget_id}, 
                       order_by=('entry_date', False),
                       limit=pagination['per_page'], offset=pagination['offset'])
    
    # Enhance entries with additional data and parse datetime
    for entry in entries:
        if entry.get('created_by'):
            creator = fetch_one('users', {'id': entry['created_by']})
            entry['creator_name'] = creator.get('fullname') if creator else None
        
        if entry.get('approved_by'):
            approver = fetch_one('users', {'id': entry['approved_by']})
            entry['approver_name'] = approver.get('fullname') if approver else None
        
        if entry.get('project_id'):
            project = fetch_one('projects', {'id': entry['project_id']})
            entry['project_name'] = project.get('name') if project else None
        
        # Parse datetime fields
        entry['entry_date_dt'] = parse_datetime(entry.get('entry_date'))
        entry['approved_at_dt'] = parse_datetime(entry.get('approved_at'))
    
    # Get projects linked to this budget
    project_allocations = fetch_all('project_budgets', {'budget_id': budget_id}, order_by=('created_at', False))
    
    # Enhance allocations with additional data and parse datetime
    for allocation in project_allocations:
        if allocation.get('project_id'):
            project = fetch_one('projects', {'id': allocation['project_id']})
            allocation['project_name'] = project.get('name') if project else None
            allocation['project_status'] = project.get('status') if project else None
        
        if allocation.get('approved_by'):
            approver = fetch_one('users', {'id': allocation['approved_by']})
            allocation['approver_name'] = approver.get('fullname') if approver else None
        
        # Parse datetime fields
        allocation['created_at_dt'] = parse_datetime(allocation.get('created_at'))
        allocation['approved_at_dt'] = parse_datetime(allocation.get('approved_at'))
    
    # Get activity history for this budget
    activity_history = fetch_all('budget_activity_history', {'budget_id': budget_id}, 
                                order_by=('performed_at', False), limit=20)
    
    # Parse datetime for activity history
    for activity in activity_history:
        activity['performed_at_dt'] = parse_datetime(activity.get('performed_at'))
    
    # Calculate statistics
    entries_all = fetch_all('budget_entries', {'budget_id': budget_id})
    total_income = 0
    total_expenses = 0
    pending_count = 0
    
    for entry in entries_all:
        if entry.get('status') == 'approved':
            if entry.get('entry_type') == 'increase':
                total_income += float(entry.get('amount', 0))
            elif entry.get('entry_type') == 'decrease':
                total_expenses += float(entry.get('amount', 0))
        elif entry.get('status') == 'pending':
            pending_count += 1
    
    stats = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'pending_count': pending_count
    }
    
    # Get all projects for allocation dropdown
    projects = fetch_all('projects', order_by='name')
    
    return render_template('budgets/budget_details.html',
                         budget=budget,
                         entries=entries,
                         project_allocations=project_allocations,
                         activity_history=activity_history,
                         stats=stats,
                         projects=projects,
                         sidebar_open=sidebar_open,
                         pagination=pagination,
                         min=min)

# --- BUDGET ENTRY APPROVAL ROUTES ---
@app.route('/budgets/<int:budget_id>/entries/<int:entry_id>/approve', methods=['POST'])
@login_required(role='SK_Chairman')
def approve_budget_entry(budget_id, entry_id):
    # Get entry and budget details
    entry = fetch_one('budget_entries', {'id': entry_id, 'budget_id': budget_id})
    
    if not entry:
        flash('Entry not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    if entry.get('status') != 'pending':
        flash('This entry is not pending approval', 'info')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    budget = fetch_one('budgets', {'id': budget_id})
    if not budget:
        flash('Budget not found', 'danger')
        return redirect(url_for('budgets'))
    
    # Get old balance for logging
    old_balance = float(budget.get('current_balance', 0))
    
    # Log approval activity BEFORE updating
    log_budget_entry_activity(entry_id, 'approve', session['user']['id'])
    
    # Update entry status
    update_data('budget_entries', entry_id, {
        'status': 'approved',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Update budget balance
    if entry.get('entry_type') == 'increase':
        new_balance = old_balance + float(entry.get('amount', 0))
    else:
        # Check if budget has sufficient balance for decrease
        if old_balance < float(entry.get('amount', 0)):
            flash('Insufficient budget balance for this expense', 'danger')
            # Revert the approval
            update_data('budget_entries', entry_id, {'status': 'pending', 'approved_by': None, 'approved_at': None})
            return redirect(url_for('budget_details', budget_id=budget_id))
        new_balance = old_balance - float(entry.get('amount', 0))
    
    update_data('budgets', budget_id, {'current_balance': new_balance})
    
    # Log balance change activity
    log_budget_activity(
        budget_id=budget_id,
        description=f"Budget entry approved: {entry.get('description', 'No description')}",
        performer_id=session['user']['id'],
        amount_changed=float(entry.get('amount', 0)),
        entry_type='entry_approved',
        old_balance=old_balance,
        new_balance=new_balance
    )
    
    flash('Budget entry approved successfully!', 'success')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

@app.route('/budgets/<int:budget_id>/entries/<int:entry_id>/reject', methods=['POST'])
@login_required(role='SK_Chairman')
def reject_budget_entry(budget_id, entry_id):
    entry = fetch_one('budget_entries', {'id': entry_id, 'budget_id': budget_id})
    
    if not entry:
        flash('Entry not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    if entry.get('status') != 'pending':
        flash('This entry is not pending approval', 'info')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Log rejection activity
    log_budget_entry_activity(entry_id, 'reject', session['user']['id'])
    
    # Update entry status to rejected
    update_data('budget_entries', entry_id, {
        'status': 'rejected',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    flash('Budget entry rejected successfully!', 'info')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

# --- PROJECT ALLOCATION APPROVAL ROUTES ---
@app.route('/budgets/<int:budget_id>/project_allocation/<int:allocation_id>/approve', methods=['POST'])
@login_required(role='SK_Chairman')
def approve_project_allocation(budget_id, allocation_id):
    # Get allocation details
    allocation = fetch_one('project_budgets', {'id': allocation_id, 'budget_id': budget_id})
    
    if not allocation:
        flash('Allocation not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    budget = fetch_one('budgets', {'id': budget_id})
    project = fetch_one('projects', {'id': allocation.get('project_id')})
    
    if not budget or not project:
        flash('Budget or project not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Check if budget has sufficient balance
    allocated_amount = float(allocation.get('allocated_amount', 0))
    current_balance = float(budget.get('current_balance', 0))
    
    if allocated_amount > current_balance:
        flash(f'Insufficient budget balance. Available: ₱{current_balance:,.2f}', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Create a decrease entry for the allocation (approved)
    entry_data = {
        'budget_id': budget_id,
        'entry_type': 'decrease',
        'amount': allocated_amount,
        'description': f'Budget allocation to project: {project.get("name")}',
        'entry_date': datetime.now().date().strftime('%Y-%m-%d'),
        'status': 'approved',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'created_by': session['user']['id'],
        'project_id': allocation.get('project_id')
    }
    
    entry_result = insert_data('budget_entries', entry_data)
    
    # Log entry creation and approval
    if entry_result:
        log_budget_entry_activity(entry_result['id'], 'create', session['user']['id'])
        log_budget_entry_activity(entry_result['id'], 'approve', session['user']['id'])
    
    # Update budget balance
    new_balance = current_balance - allocated_amount
    update_data('budgets', budget_id, {'current_balance': new_balance})
    
    # Update allocation status to approved
    update_data('project_budgets', allocation_id, {
        'status': 'approved',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Log allocation approval activity
    log_budget_activity(
        budget_id=budget_id,
        description=f"Project allocation approved: {project.get('name')} - ₱{allocated_amount:,.2f}",
        performer_id=session['user']['id'],
        amount_changed=allocated_amount,
        entry_type='project_allocation_approved',
        old_balance=current_balance,
        new_balance=new_balance
    )
    
    flash('Project allocation approved successfully!', 'success')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

@app.route('/budgets/<int:budget_id>/project_allocation/<int:allocation_id>/reject', methods=['POST'])
@login_required(role='SK_Chairman')
def reject_project_allocation(budget_id, allocation_id):
    allocation = fetch_one('project_budgets', {'id': allocation_id, 'budget_id': budget_id})
    
    if not allocation:
        flash('Allocation not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    project = fetch_one('projects', {'id': allocation.get('project_id')}) if allocation.get('project_id') else None
    
    # Log rejection activity
    log_budget_activity(
        budget_id=budget_id,
        description=f"Project allocation rejected: {project.get('name', 'Unknown project') if project else 'Unknown project'} - ₱{allocation.get('allocated_amount', 0):,.2f}",
        performer_id=session['user']['id'],
        amount_changed=0,
        entry_type='project_allocation_rejected'
    )
    
    # Update allocation status to rejected
    update_data('project_budgets', allocation_id, {
        'status': 'rejected',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    flash('Project allocation rejected successfully!', 'info')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

@app.route('/budgets/<int:budget_id>/allocate_project', methods=['POST'])
@login_required()
def allocate_project_budget(budget_id):
    # Only SK_Chairman, Treasurer, BMO, and super_admin can allocate budgets
    if session['user']['role'] not in ['SK_Chairman', 'Treasurer', 'BMO', 'super_admin']:
        flash('Access denied: Only SK Chairman, Treasurer, BMO, and Super Admin can allocate budgets', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    project_id = request.form.get('project_id')
    amount = request.form.get('amount', '0').strip()
    
    if not project_id or not amount:
        flash('Please select a project and specify amount', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    try:
        amount = Decimal(amount)
    except:
        flash('Invalid amount', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    budget = fetch_one('budgets', {'id': budget_id})
    project = fetch_one('projects', {'id': project_id})
    
    if not budget or not project:
        flash('Budget or project not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Check if project already has pending or approved allocation
    existing_allocations = fetch_all('project_budgets', {'project_id': project_id, 'budget_id': budget_id})
    for existing in existing_allocations:
        if existing.get('status') in ['pending', 'approved']:
            status_text = 'pending' if existing['status'] == 'pending' else 'approved'
            flash(f'This project already has a {status_text} allocation from this budget', 'danger')
            return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Create pending allocation (not approved yet)
    allocation_data = {
        'project_id': project_id,
        'budget_id': budget_id,
        'allocated_amount': float(amount),
        'status': 'pending',
        'created_by': session['user']['id']
    }
    
    print(f"DEBUG allocate_project_budget(): Creating allocation: {allocation_data}")
    
    result = insert_data('project_budgets', allocation_data)
    
    # Log allocation request activity
    if result:
        log_budget_activity(
            budget_id=budget_id,
            description=f"Project allocation requested: {project.get('name')} - ₱{amount:,.2f}",
            performer_id=session['user']['id'],
            amount_changed=float(amount),
            entry_type='project_allocation_requested'
        )
    
    flash(f'Project allocation created successfully! Status: Pending (requires SK Chairman approval)', 'success')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

@app.route('/budgets/<int:budget_id>/project_allocation/<int:allocation_id>/delete')
@login_required()
def delete_project_allocation(budget_id, allocation_id):
    # Only SK_Chairman, Treasurer, BMO, and super_admin can delete allocations
    if session['user']['role'] not in ['SK_Chairman', 'Treasurer', 'BMO', 'super_admin']:
        flash('Access denied: Only SK Chairman, Treasurer, BMO, and Super Admin can manage allocations', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Get allocation details
    allocation = fetch_one('project_budgets', {'id': allocation_id, 'budget_id': budget_id})
    
    if not allocation:
        flash('Allocation not found', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    # Only allow deletion of approved allocations
    if allocation.get('status') != 'approved':
        flash('Only approved allocations can be removed', 'danger')
        return redirect(url_for('budget_details', budget_id=budget_id))
    
    budget = fetch_one('budgets', {'id': budget_id})
    if not budget:
        flash('Budget not found', 'danger')
        return redirect(url_for('budgets'))
    
    project = fetch_one('projects', {'id': allocation.get('project_id')}) if allocation.get('project_id') else None
    
    # Log allocation removal
    log_budget_activity(
        budget_id=budget_id,
        description=f"Project allocation removed: {project.get('name', 'Unknown project') if project else 'Unknown project'} - ₱{allocation.get('allocated_amount', 0):,.2f} returned to budget",
        performer_id=session['user']['id'],
        amount_changed=float(allocation.get('allocated_amount', 0)),
        entry_type='project_allocation_removed'
    )
    
    # Return allocated amount to budget (create increase entry)
    entry_data = {
        'budget_id': budget_id,
        'entry_type': 'increase',
        'amount': float(allocation.get('allocated_amount', 0)),
        'description': f'Returned allocation from project #{allocation.get("project_id")}',
        'entry_date': datetime.now().date().strftime('%Y-%m-%d'),
        'status': 'approved',
        'approved_by': session['user']['id'],
        'approved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'created_by': session['user']['id'],
        'project_id': allocation.get('project_id')
    }
    
    entry_result = insert_data('budget_entries', entry_data)
    
    # Log entry creation and approval
    if entry_result:
        log_budget_entry_activity(entry_result['id'], 'create', session['user']['id'])
        log_budget_entry_activity(entry_result['id'], 'approve', session['user']['id'])
    
    # Update budget balance
    old_balance = float(budget.get('current_balance', 0))
    new_balance = old_balance + float(allocation.get('allocated_amount', 0))
    update_data('budgets', budget_id, {'current_balance': new_balance})
    
    # Delete allocation
    delete_data('project_budgets', allocation_id)
    
    flash('Project allocation removed successfully!', 'info')
    return redirect(url_for('budget_details', budget_id=budget_id) + '?sidebar=open')

@app.route('/monthly_financial_reports/new', methods=['GET', 'POST'])
@login_required()
def new_monthly_financial_report():
    sidebar_open = request.args.get('sidebar') == 'open'
    
    if request.method == 'POST':
        year = request.form.get('year', '').strip()
        month = request.form.get('month', '').strip()
        notes = request.form.get('notes', '').strip()
        file = request.files.get('file')
        
        if not year or not month:
            flash('Please select both year and month', 'danger')
            return redirect(url_for('new_monthly_financial_report'))
        
        month_year = f"{year}-{month:0>2}"
        
        # Check if report already exists for this month
        existing_report = fetch_one('monthly_financial_reports', {'month_year': month_year})
        
        if existing_report:
            flash(f'A monthly financial report for {month_year} already exists!', 'warning')
            return redirect(url_for('new_monthly_financial_report'))
        
        # Calculate financial data
        # Get total income for the month (approved increases)
        all_entries = fetch_all('budget_entries')
        total_income = 0
        total_expenses = 0
        
        for entry in all_entries:
            if entry.get('status') == 'approved':
                entry_date = entry.get('entry_date')
                if entry_date:
                    entry_date_dt = parse_datetime(entry_date)
                    if entry_date_dt and entry_date_dt.year == int(year) and entry_date_dt.month == int(month):
                        if entry.get('entry_type') == 'increase':
                            total_income += float(entry.get('amount', 0))
                        elif entry.get('entry_type') == 'decrease':
                            total_expenses += float(entry.get('amount', 0))
        
        # Simple calculation for opening and closing balance
        opening_balance = 0  # This would need more complex calculation
        closing_balance = opening_balance + total_income - total_expenses
        
        # Handle file upload
        filename_db = None
        if file and file.filename:
            if allowed_file(file.filename):
                safe = secure_filename(file.filename)
                dest = os.path.join(REPORT_UPLOADS, safe)
                file.save(dest)
                filename_db = f'uploads/reports/{safe}'
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('new_monthly_financial_report'))
        
        # Create the monthly financial report
        report_data = {
            'month_year': month_year,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'notes': notes,
            'filename': filename_db,
            'created_by': session['user']['id']
        }
        
        insert_data('monthly_financial_reports', report_data)
        
        # Also create a regular report entry
        regular_report = {
            'type': 'Monthly Financial Report',
            'filename': filename_db,
            'uploaded_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'reported_for': f'Financial Report for {month_year}',
            'notes': notes,
            'created_by': session['user']['id']
        }
        
        insert_data('reports', regular_report)
        
        flash(f'Monthly financial report for {month_year} created successfully!', 'success')
        return redirect(url_for('reports') + '?sidebar=open')
    
    # Get available years and months with budget activity
    all_entries = fetch_all('budget_entries')
    years_set = set()
    months_set = set()
    
    for entry in all_entries:
        entry_date = entry.get('entry_date')
        if entry_date:
            entry_date_dt = parse_datetime(entry_date)
            if entry_date_dt:
                years_set.add(entry_date_dt.year)
                months_set.add(entry_date_dt.month)
    
    years = sorted(list(years_set), reverse=True)
    months = sorted(list(months_set))
    
    # Get months that already have reports to disable them
    existing_reports = fetch_all('monthly_financial_reports')
    existing_report_months = [report['month_year'] for report in existing_reports]
    
    # Month names for display
    month_names = {
        '1': 'January', '2': 'February', '3': 'March', '4': 'April',
        '5': 'May', '6': 'June', '7': 'July', '8': 'August',
        '9': 'September', '10': 'October', '11': 'November', '12': 'December'
    }
    
    return render_template('budgets/new_monthly_financial_report.html', 
                         years=years,
                         months=months,
                         month_names=month_names,
                         existing_reports=existing_report_months,
                         sidebar_open=sidebar_open)

@app.route('/monthly_financial_reports')
@login_required()
def monthly_financial_reports():
    reports = fetch_all('monthly_financial_reports', order_by=('month_year', False))
    
    sidebar_open = request.args.get('sidebar') == 'open'
    return render_template('budgets/monthly_financial_reports.html', 
                         reports=reports,
                         sidebar_open=sidebar_open)

# --- FIX FILE VIEW ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve files correctly from static/uploads."""
    safe_path = os.path.join(app.static_folder, 'uploads')
    return send_from_directory(safe_path, filename, as_attachment=False)

# --- Serve budget evidence files ---
@app.route('/uploads/budget_evidence/<filename>')
def serve_budget_evidence(filename):
    """Serve budget evidence files from the correct directory"""
    return send_from_directory(BUDGET_EVIDENCE_UPLOADS, filename, as_attachment=False)

# --- Run ---
if __name__ == '__main__':
    app.run(debug=True, port=5001)