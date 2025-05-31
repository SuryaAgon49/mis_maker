from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
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
from jinja2 import Template

app = Flask(__name__)
app.config['SECRET_KEY'] = '99eca62134091c78614e29a7030ebacf198af33e84cd8dcbf7104f8043354835'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///company_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Fixed Admin Credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Database Model - Redesigned for Company Data
class CompanyData(db.Model):
    __tablename__ = 'company_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    week = db.Column(db.String(20), nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    contact_number = db.Column(db.String(50), nullable=False)
    designated_person_name = db.Column(db.String(100), nullable=True)  # Can be blank
    designation = db.Column(db.String(100), nullable=True)  # Position
    address = db.Column(db.Text, nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'week': self.week,
            'company_name': self.company_name,
            'contact_number': self.contact_number,
            'designated_person_name': self.designated_person_name,
            'designation': self.designation,
            'address': self.address,
            'remarks': self.remarks,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

# Helper Functions
def get_week_number(date):
    """Get week number in format YYYY-W##"""
    return f"{date.year}-W{date.isocalendar()[1]:02d}"

def get_current_week():
    """Get current week string"""
    return get_week_number(datetime.now())

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
    companies_with_contacts = len([d for d in data if d.designated_person_name])
    
    summary_text = f"<b>Summary:</b><br/>Total Companies: {total_companies}<br/>Companies with Designated Contacts: {companies_with_contacts}"
    story.append(Paragraph(summary_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Create table data
    if data:
        # Table headers
        table_data = [['Date', 'Company Name', 'Contact Number', 'Contact Person', 'Designation', 'Address', 'Remarks']]
        
        # Add data rows
        for entry in data:
            row = [
                entry.date.strftime('%Y-%m-%d'),
                entry.company_name[:20] + '...' if len(entry.company_name) > 20 else entry.company_name,
                entry.contact_number,
                (entry.designated_person_name or '')[:15] + '...' if entry.designated_person_name and len(entry.designated_person_name) > 15 else (entry.designated_person_name or ''),
                (entry.designation or '')[:15] + '...' if entry.designation and len(entry.designation) > 15 else (entry.designation or ''),
                (entry.address or '')[:25] + '...' if entry.address and len(entry.address) > 25 else (entry.address or ''),
                (entry.remarks or '')[:20] + '...' if entry.remarks and len(entry.remarks) > 20 else (entry.remarks or '')
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
    
    # Get summary statistics
    total_companies = CompanyData.query.count()
    companies_with_contacts = CompanyData.query.filter(CompanyData.designated_person_name != '').filter(CompanyData.designated_person_name.isnot(None)).count()
    current_week_entries = CompanyData.query.filter_by(week=get_current_week()).count()
    
    # Get data for charts
    # Weekly trend data
    weekly_data = db.session.query(
        CompanyData.week,
        db.func.count(CompanyData.id).label('count')
    ).group_by(CompanyData.week).order_by(CompanyData.week).all()
    
    # Companies by designation
    designation_data = db.session.query(
        CompanyData.designation,
        db.func.count(CompanyData.id).label('count')
    ).filter(CompanyData.designation != '').filter(CompanyData.designation.isnot(None)).group_by(CompanyData.designation).all()
    
    # Recent companies
    recent_companies = CompanyData.query.order_by(CompanyData.timestamp.desc()).limit(5).all()
    
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
                        
                        week_str = get_week_number(date_obj)
                        
                        entry = CompanyData(
                            date=date_obj,
                            week=week_str,
                            company_name=row.get('company_name', '').strip(),
                            contact_number=row.get('contact_number', '').strip(),
                            designated_person_name=row.get('designated_person_name', '').strip(),
                            designation=row.get('designation', '').strip(),
                            address=row.get('address', '').strip(),
                            remarks=row.get('remarks', '').strip()
                        )
                        db.session.add(entry)
                        added_count += 1
                    except Exception as e:
                        print(f"Error adding row: {e}")
                        continue
                
                db.session.commit()
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
                week_str = get_week_number(date_obj)
                
                entry = CompanyData(
                    date=date_obj,
                    week=week_str,
                    company_name=request.form['company_name'].strip(),
                    contact_number=request.form['contact_number'].strip(),
                    designated_person_name=request.form.get('designated_person_name', '').strip(),
                    designation=request.form.get('designation', '').strip(),
                    address=request.form['address'].strip(),
                    remarks=request.form.get('remarks', '').strip()
                )
                
                db.session.add(entry)
                db.session.commit()
                flash('Company entry added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding entry: {e}', 'error')
        
        return redirect(url_for('data_entry'))
    
    # Get recent entries for display
    recent_entries = CompanyData.query.order_by(CompanyData.timestamp.desc()).limit(10).all()
    return render_template('data_entry.html', recent_entries=recent_entries)

@app.route('/export')
def export():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get available weeks
    weeks = db.session.query(CompanyData.week).distinct().order_by(CompanyData.week.desc()).all()
    weeks = [w[0] for w in weeks]
    
    return render_template('export.html', weeks=weeks)

@app.route('/export_data')
def export_data():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    week = request.args.get('week')
    format_type = request.args.get('format', 'excel')
    
    # Build query
    query = CompanyData.query
    if week and week != 'all':
        query = query.filter_by(week=week)
    
    data = query.order_by(CompanyData.date.desc()).all()
    
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
            worksheet.write(row, 0, entry.date.strftime('%Y-%m-%d'))
            worksheet.write(row, 1, entry.week)
            worksheet.write(row, 2, entry.company_name)
            worksheet.write(row, 3, entry.contact_number)
            worksheet.write(row, 4, entry.designated_person_name or '')
            worksheet.write(row, 5, entry.designation or '')
            worksheet.write(row, 6, entry.address or '')
            worksheet.write(row, 7, entry.remarks or '')
        
        # Auto-adjust column widths
        column_widths = [12, 12, 25, 15, 20, 15, 30, 25]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        workbook.close()
        output.seek(0)
        
        filename = f"company_directory_{week or 'all'}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    elif format_type == 'pdf':
        # Create PDF report using ReportLab
        pdf_buffer = create_pdf_report(data, week)
        filename = f"company_report_{week or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/api/chart_data')
def chart_data():
    if 'logged_in' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    chart_type = request.args.get('type')
    
    if chart_type == 'weekly_trend':
        data = db.session.query(
            CompanyData.week,
            db.func.count(CompanyData.id).label('count')
        ).group_by(CompanyData.week).order_by(CompanyData.week).all()
        
        return jsonify({
            'labels': [d.week for d in data],
            'data': [d.count for d in data]
        })
    
    elif chart_type == 'designation_distribution':
        data = db.session.query(
            CompanyData.designation,
            db.func.count(CompanyData.id).label('count')
        ).filter(CompanyData.designation != '').filter(CompanyData.designation.isnot(None)).group_by(CompanyData.designation).all()
        
        return jsonify({
            'labels': [d.designation for d in data],
            'data': [d.count for d in data]
        })
    
    elif chart_type == 'contact_status':
        with_contact = CompanyData.query.filter(CompanyData.designated_person_name != '').filter(CompanyData.designated_person_name.isnot(None)).count()
        without_contact = CompanyData.query.filter(
            db.or_(CompanyData.designated_person_name == '', CompanyData.designated_person_name.is_(None))
        ).count()
        
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
    
    # Build query
    query = CompanyData.query
    if week and week != 'all':
        query = query.filter_by(week=week)
    
    data = query.order_by(CompanyData.date.desc()).limit(50).all()
    
    return jsonify([entry.to_dict() for entry in data])

@app.route('/companies')
def companies():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = CompanyData.query
    
    if search:
        query = query.filter(
            db.or_(
                CompanyData.company_name.contains(search),
                CompanyData.designated_person_name.contains(search),
                CompanyData.contact_number.contains(search)
            )
        )
    
    companies = query.order_by(CompanyData.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('companies.html', companies=companies, search=search)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Company Directory System starting...")
    print("Login credentials: admin / admin123")
    print("New database structure with Company Name, Contact Number, Designated Person Name, Designation, Address, and Remarks")
    app.run(debug=True)
