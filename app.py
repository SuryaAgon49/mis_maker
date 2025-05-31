from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from datetime import datetime, timedelta
import pandas as pd
import os
from werkzeug.utils import secure_filename
import json
from io import BytesIO
import xlsxwriter
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from collections import defaultdict
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Fixed Admin Credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# In-memory data storage
DATA_FILE = 'company_data.json'
company_data = []

# Data persistence functions
def load_data():
    """Load data from JSON file"""
    global company_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert date strings back to datetime objects for processing
                for item in data:
                    if item.get('date'):
                        item['date'] = datetime.strptime(item['date'], '%Y-%m-%d').date()
                    if item.get('timestamp'):
                        item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                    else:
                        item['timestamp'] = datetime.utcnow()
                company_data = data
    except Exception as e:
        print(f"Error loading data: {e}")
        company_data = []

def save_data():
    """Save data to JSON file"""
    try:
        # Convert datetime objects to strings for JSON serialization
        data_to_save = []
        for item in company_data:
            item_copy = item.copy()
            if item_copy.get('date') and hasattr(item_copy['date'], 'isoformat'):
                item_copy['date'] = item_copy['date'].isoformat()
            if item_copy.get('timestamp') and hasattr(item_copy['timestamp'], 'isoformat'):
                item_copy['timestamp'] = item_copy['timestamp'].isoformat()
            data_to_save.append(item_copy)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving data: {e}")

# Company Data Class (replacing SQLAlchemy model)
class CompanyDataModel:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        self.date = kwargs.get('date', datetime.now().date())
        self.week = kwargs.get('week', get_week_number(self.date))
        self.company_name = kwargs.get('company_name', '')
        self.contact_number = kwargs.get('contact_number', '')
        self.designated_person_name = kwargs.get('designated_person_name', '')
        self.designation = kwargs.get('designation', '')
        self.address = kwargs.get('address', '')
        self.remarks = kwargs.get('remarks', '')
        self.timestamp = kwargs.get('timestamp', datetime.utcnow())
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if hasattr(self.date, 'isoformat') else str(self.date),
            'week': self.week,
            'company_name': self.company_name,
            'contact_number': self.contact_number,
            'designated_person_name': self.designated_person_name,
            'designation': self.designation,
            'address': self.address,
            'remarks': self.remarks,
            'timestamp': self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp)
        }

# Data access functions (replacing SQLAlchemy queries)
def get_all_companies():
    """Get all companies"""
    return company_data

def get_companies_by_week(week):
    """Get companies by week"""
    return [item for item in company_data if item.get('week') == week]

def get_companies_count():
    """Get total companies count"""
    return len(company_data)

def get_companies_with_contacts_count():
    """Get count of companies with designated person"""
    return len([item for item in company_data if item.get('designated_person_name', '').strip()])

def get_current_week_count():
    """Get current week entries count"""
    current_week = get_current_week()
    return len([item for item in company_data if item.get('week') == current_week])

def get_weekly_data():
    """Get weekly trend data"""
    weekly_counts = defaultdict(int)
    for item in company_data:
        weekly_counts[item.get('week', '')] += 1
    return [(week, count) for week, count in sorted(weekly_counts.items())]

def get_designation_data():
    """Get designation distribution data"""
    designation_counts = defaultdict(int)
    for item in company_data:
        designation = item.get('designation', '').strip()
        if designation:
            designation_counts[designation] += 1
    return [(designation, count) for designation, count in designation_counts.items()]

def get_recent_companies(limit=5):
    """Get recent companies"""
    sorted_data = sorted(company_data, key=lambda x: x.get('timestamp', datetime.min), reverse=True)
    return sorted_data[:limit]

def get_unique_weeks():
    """Get unique weeks"""
    weeks = set()
    for item in company_data:
        if item.get('week'):
            weeks.add(item['week'])
    return sorted(list(weeks), reverse=True)

def search_companies(search_term, page=1, per_page=20):
    """Search companies with pagination"""
    search_term = search_term.lower()
    filtered_data = []
    
    for item in company_data:
        if (search_term in item.get('company_name', '').lower() or
            search_term in item.get('designated_person_name', '').lower() or
            search_term in item.get('contact_number', '').lower()):
            filtered_data.append(item)
    
    # Sort by timestamp descending
    filtered_data.sort(key=lambda x: x.get('timestamp', datetime.min), reverse=True)
    
    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    
    return {
        'items': filtered_data[start:end],
        'total': len(filtered_data),
        'page': page,
        'per_page': per_page,
        'pages': (len(filtered_data) + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < len(filtered_data),
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page * per_page < len(filtered_data) else None
    }

def add_company(data_dict):
    """Add new company"""
    global company_data
    
    # Ensure date is proper format
    if isinstance(data_dict.get('date'), str):
        try:
            data_dict['date'] = datetime.strptime(data_dict['date'], '%Y-%m-%d').date()
        except:
            data_dict['date'] = datetime.now().date()
    
    # Generate ID and timestamp
    data_dict['id'] = str(uuid.uuid4())
    data_dict['timestamp'] = datetime.utcnow()
    data_dict['week'] = get_week_number(data_dict['date'])
    
    company_data.append(data_dict)
    save_data()

# Helper Functions
def get_week_number(date):
    """Get week number in format YYYY-W##"""
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()
    return f"{date.year}-W{date.isocalendar()[1]:02d}"

def get_current_week():
    """Get current week string"""
    return get_week_number(datetime.now().date())

def parse_excel_file(file_path):
    """Parse Excel file and return data"""
    try:
        df = pd.read_excel(file_path)
        
        # Column mapping for the new structure
        column_mapping = {
            'Company Name': 'company_name',
            'Company': 'company_name',
            'Contact Number': 'contact_number',
            'Contact': 'contact_number',
            'Phone': 'contact_number',
            'Designated Person Name': 'designated_person_name',
            'Person Name': 'designated_person_name',
            'Contact Person': 'designated_person_name',
            'Designation': 'designation',
            'Position': 'designation',
            'Title': 'designation',
            'Address': 'address',
            'Location': 'address',
            'Remarks': 'remarks',
            'Notes': 'remarks',
            'Comments': 'remarks',
            'Date': 'date'
        }
        
        # Rename columns if they exist
        for excel_col, db_col in column_mapping.items():
            if excel_col in df.columns:
                df = df.rename(columns={excel_col: db_col})
        
        # Fill missing required columns with defaults
        required_cols = ['company_name', 'contact_number', 'address']
        for col in required_cols:
            if col not in df.columns:
                if col == 'company_name':
                    df[col] = 'Unknown Company'
                elif col == 'contact_number':
                    df[col] = 'Not Provided'
                elif col == 'address':
                    df[col] = 'Address Not Provided'
        
        # Optional columns - can be blank
        if 'designated_person_name' not in df.columns:
            df['designated_person_name'] = ''
        if 'designation' not in df.columns:
            df['designation'] = ''
        if 'remarks' not in df.columns:
            df['remarks'] = ''
        if 'date' not in df.columns:
            df['date'] = datetime.now().date()
        
        # Clean up NaN values
        df = df.fillna('')
        
        return df.to_dict('records')
    except Exception as e:
        print(f"Error parsing Excel: {e}")
        return []

def create_pdf_report(data, week_filter=None):
    """Create PDF report using ReportLab"""
    buffer = BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=36, leftMargin=36, 
                          topMargin=72, bottomMargin=36)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue
    )
    
    # Build story
    story = []
    
    # Title
    title = f"Company Directory Report - {week_filter or 'All Weeks'}"
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    
    # Generated date
    gen_date = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    story.append(Paragraph(gen_date, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Summary statistics
    total_companies = len(data)
    companies_with_contacts = len([d for d in data if d.get('designated_person_name', '').strip()])
    
    summary_text = f"<b>Summary:</b><br/>Total Companies: {total_companies}<br/>Companies with Designated Contacts: {companies_with_contacts}"
    story.append(Paragraph(summary_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Create table data
    if data:
        # Table headers
        table_data = [['Date', 'Company Name', 'Contact Number', 'Contact Person', 'Designation', 'Address', 'Remarks']]
        
        # Add data rows
        for entry in data:
            date_str = entry.get('date', '')
            if hasattr(date_str, 'strftime'):
                date_str = date_str.strftime('%Y-%m-%d')
            elif isinstance(date_str, str) and len(date_str) > 10:
                date_str = date_str[:10]
            
            row = [
                str(date_str),
                (entry.get('company_name', '')[:20] + '...') if len(entry.get('company_name', '')) > 20 else entry.get('company_name', ''),
                entry.get('contact_number', ''),
                (entry.get('designated_person_name', '')[:15] + '...') if len(entry.get('designated_person_name', '')) > 15 else entry.get('designated_person_name', ''),
                (entry.get('designation', '')[:15] + '...') if len(entry.get('designation', '')) > 15 else entry.get('designation', ''),
                (entry.get('address', '')[:25] + '...') if len(entry.get('address', '')) > 25 else entry.get('address', ''),
                (entry.get('remarks', '')[:20] + '...') if len(entry.get('remarks', '')) > 20 else entry.get('remarks', '')
            ]
            table_data.append(row)
        
        # Create table with adjusted column widths
        table = Table(table_data, colWidths=[0.8*inch, 1.5*inch, 1*inch, 1.2*inch, 1*inch, 1.5*inch, 1.2*inch])
        
        # Table style
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        story.append(table)
    else:
        story.append(Paragraph("No data available for the selected criteria.", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Initialize data when app context is available
def init_app():
    """Initialize application data"""
    load_data()

# Routes
@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Ensure data is loaded
    if not company_data:
        load_data()
    
    # Get summary statistics
    total_companies = get_companies_count()
    companies_with_contacts = get_companies_with_contacts_count()
    current_week_entries = get_current_week_count()
    
    # Get data for charts
    weekly_data = get_weekly_data()
    designation_data = get_designation_data()
    recent_companies = get_recent_companies()
    
    return render_template('dashboard.html',
                         total_companies=total_companies,
                         companies_with_contacts=companies_with_contacts,
                         current_week_entries=current_week_entries,
                         weekly_data=weekly_data,
                         designation_data=designation_data,
                         recent_companies=recent_companies)

@app.route('/data_entry', methods=['GET', 'POST'])
def data_entry():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'excel_file' in request.files:
            # Handle Excel upload
            file = request.files['excel_file']
            if file and file.filename.endswith(('.xlsx', '.xls')):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Parse Excel and save to database
                excel_data = parse_excel_file(file_path)
                added_count = 0
                
                for row in excel_data:
                    try:
                        # Handle date conversion
                        if isinstance(row.get('date'), str):
                            try:
                                date_obj = datetime.strptime(row['date'], '%Y-%m-%d').date()
                            except:
                                date_obj = datetime.now().date()
                        elif pd.isna(row.get('date')) or not row.get('date'):
                            date_obj = datetime.now().date()
                        else:
                            date_obj = row.get('date', datetime.now().date())
                        
                        entry_data = {
                            'date': date_obj,
                            'company_name': str(row.get('company_name', '')).strip(),
                            'contact_number': str(row.get('contact_number', '')).strip(),
                            'designated_person_name': str(row.get('designated_person_name', '')).strip(),
                            'designation': str(row.get('designation', '')).strip(),
                            'address': str(row.get('address', '')).strip(),
                            'remarks': str(row.get('remarks', '')).strip()
                        }
                        
                        add_company(entry_data)
                        added_count += 1
                    except Exception as e:
                        print(f"Error adding row: {e}")
                        continue
                
                flash(f'Successfully added {added_count} company entries from Excel!', 'success')
                
                # Clean up uploaded file
                try:
                    os.remove(file_path)
                except:
                    pass
                
        else:
            # Handle manual entry
            try:
                date_str = request.form['date']
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                entry_data = {
                    'date': date_obj,
                    'company_name': request.form['company_name'].strip(),
                    'contact_number': request.form['contact_number'].strip(),
                    'designated_person_name': request.form.get('designated_person_name', '').strip(),
                    'designation': request.form.get('designation', '').strip(),
                    'address': request.form['address'].strip(),
                    'remarks': request.form.get('remarks', '').strip()
                }
                
                add_company(entry_data)
                flash('Company entry added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding entry: {e}', 'error')
        
        return redirect(url_for('data_entry'))
    
    # Get recent entries for display
    recent_entries = get_recent_companies(10)
    return render_template('data_entry.html', recent_entries=recent_entries)

@app.route('/export')
def export():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get available weeks
    weeks = get_unique_weeks()
    
    return render_template('export.html', weeks=weeks)

@app.route('/export_data')
def export_data():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    week = request.args.get('week')
    format_type = request.args.get('format', 'excel')
    
    # Get data
    if week and week != 'all':
        data = get_companies_by_week(week)
    else:
        data = get_all_companies()
    
    # Sort by date descending
    data = sorted(data, key=lambda x: x.get('timestamp', datetime.min), reverse=True)
    
    if format_type == 'excel':
        # Create Excel file
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Company Directory')
        
        # Add header format
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center'
        })
        
        # Headers
        headers = ['Date', 'Week', 'Company Name', 'Contact Number', 'Designated Person Name', 'Designation', 'Address', 'Remarks']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        for row, entry in enumerate(data, 1):
            date_str = entry.get('date', '')
            if hasattr(date_str, 'strftime'):
                date_str = date_str.strftime('%Y-%m-%d')
            elif isinstance(date_str, str) and len(date_str) > 10:
                date_str = date_str[:10]
            
            worksheet.write(row, 0, str(date_str))
            worksheet.write(row, 1, entry.get('week', ''))
            worksheet.write(row, 2, entry.get('company_name', ''))
            worksheet.write(row, 3, entry.get('contact_number', ''))
            worksheet.write(row, 4, entry.get('designated_person_name', ''))
            worksheet.write(row, 5, entry.get('designation', ''))
            worksheet.write(row, 6, entry.get('address', ''))
            worksheet.write(row, 7, entry.get('remarks', ''))
        
        # Auto-adjust column widths
        column_widths = [12, 12, 25, 15, 20, 15, 30, 25]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        workbook.close()
        output.seek(0)
        
        filename = f"company_directory_{week or 'all'}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    elif format_type == 'pdf':
        # Create PDF report
        pdf_buffer = create_pdf_report(data, week)
        filename = f"company_report_{week or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/api/chart_data')
def chart_data():
    if 'logged_in' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    chart_type = request.args.get('type')
    
    if chart_type == 'weekly_trend':
        data = get_weekly_data()
        return jsonify({
            'labels': [d[0] for d in data],
            'data': [d[1] for d in data]
        })
    
    elif chart_type == 'designation_distribution':
        data = get_designation_data()
        return jsonify({
            'labels': [d[0] for d in data],
            'data': [d[1] for d in data]
        })
    
    elif chart_type == 'contact_status':
        with_contact = get_companies_with_contacts_count()
        without_contact = get_companies_count() - with_contact
        
        return jsonify({
            'labels': ['With Contact Person', 'Without Contact Person'],
            'data': [with_contact, without_contact]
        })
    
    return jsonify({'error': 'Invalid chart type'}), 400

@app.route('/api/preview_data')
def preview_data():
    if 'logged_in' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    week = request.args.get('week')
    
    # Get data
    if week and week != 'all':
        data = get_companies_by_week(week)
    else:
        data = get_all_companies()
    
    # Sort and limit
    data = sorted(data, key=lambda x: x.get('timestamp', datetime.min), reverse=True)[:50]
    
    # Convert to dict format for JSON response
    result = []
    for entry in data:
        entry_dict = entry.copy()
        # Ensure proper date format for JSON
        if entry_dict.get('date') and hasattr(entry_dict['date'], 'isoformat'):
            entry_dict['date'] = entry_dict['date'].isoformat()
        if entry_dict.get('timestamp') and hasattr(entry_dict['timestamp'], 'isoformat'):
            entry_dict['timestamp'] = entry_dict['timestamp'].isoformat()
        result.append(entry_dict)
    
    return jsonify(result)

@app.route('/companies')
def companies():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    # Get paginated results
    companies_data = search_companies(search, page, 20)
    
    # Create a simple object to mimic SQLAlchemy pagination
    class PaginationObject:
        def __init__(self, data):
            self.items = data['items']
            self.total = data['total']
            self.page = data['page']
            self.per_page = data['per_page']
            self.pages = data['pages']
            self.has_prev = data['has_prev']
            self.has_next = data['has_next']
            self.prev_num = data['prev_num']
            self.next_num = data['next_num']
        
        def iter_pages(self):
            """Generator for pagination numbers"""
            for num in range(1, self.pages + 1):
                yield num
    
    companies = PaginationObject(companies_data)
    
    return render_template('companies.html', companies=companies, search=search)

if __name__ == '__main__':
    # Initialize data on startup
    init_app()
    print("Company Directory System starting...")
    print("Login credentials: admin / admin123")
    print("Database-free version using JSON file storage")
    print("New database structure with Company Name, Contact Number, Designated Person Name, Designation, Address, and Remarks")
    app.run(debug=True, host='0.0.0.0', port=5000)
