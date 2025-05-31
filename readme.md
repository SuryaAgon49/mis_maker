# SmartMIS - Project Structure & Setup

## 📁 Folder Structure
```
SmartMIS/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── database.db              # SQLite database (auto-created)
├── templates/               # HTML templates
│   ├── login.html
│   ├── dashboard.html
│   ├── data_entry.html
│   └── export.html
├── static/                  # Static files (CSS, JS, images)
│   └── css/                # Custom CSS files (optional)
└── uploads/                # Uploaded Excel files (auto-created)
```

## 🚀 Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Access the Application
- Open browser and go to: `http://localhost:5000`
- Login with:
  - **Username:** admin
  - **Password:** admin123

## 🔧 Key Features

### Authentication
- Fixed admin login (hardcoded credentials)
- Session-based authentication
- Auto-redirect to login if not authenticated

### Data Entry
- **Manual Entry:** Web form with validation
- **Excel Upload:** Supports .xlsx and .xls files
- **Auto-tagging:** Week numbers and timestamps
- **Recent Entries:** View last 10 entries

### Database Schema
```sql
CREATE TABLE weekly_data (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    week VARCHAR(20) NOT NULL,
    customer VARCHAR(100) NOT NULL,
    product VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    revenue FLOAT DEFAULT 0.0,
    notes TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Dashboard Analytics
- **Summary Cards:** Total entries, revenue, current week count
- **Weekly Trend:** Line chart showing revenue over time
- **Region Distribution:** Bar chart of customers by region
- **Status Breakdown:** Pie chart of status distribution

### Export Features
- **Excel Export:** Download as .xlsx with all data
- **PDF Reports:** Formatted reports with tables
- **Week Filtering:** Export specific weeks or all data
- **Quick Export:** One-click current week/all data exports

## 📊 Expected Excel Format

When uploading Excel files, the following columns are expected:
- **Customer** - Customer name
- **Product** - Product name
- **Region** - North/South/East/West/Central
- **Status** - Active/Pending/Completed/Cancelled
- **Revenue** - Numeric revenue value
- **Notes** - Additional notes (optional)
- **Date** - Date in YYYY-MM-DD format (optional, defaults to today)

## 🔒 Security Notes
- Login credentials are hardcoded in app.py
- SQLite database has no encryption
- File uploads are stored in uploads/ folder
- Session secret key should be changed in production

## 🛠️ Customization

### Adding New Fields
1. Update the `WeeklyData` model in app.py
2. Update HTML forms in templates
3. Update Excel parsing logic
4. Run `db.create_all()` to update schema

### Changing Login Credentials
```python
ADMIN_USERNAME = 'your_username'
ADMIN_PASSWORD = 'your_password'
```

### Adding New Chart Types
1. Add new query in dashboard route
2. Add Chart.js code in dashboard.html
3. Optionally add API endpoint for dynamic data

## 📈 Usage Workflow

1. **Login** → Enter admin credentials
2. **Data Entry** → Add data manually or upload Excel
3. **Dashboard** → View analytics and trends
4. **Export** → Generate weekly/monthly reports

## 🔧 Troubleshooting

### Common Issues
- **Database not found:** Run the app once to auto-create database.db
- **Upload folder error:** Ensure uploads/ folder exists or app will create it
- **Excel parsing error:** Check column names match expected format
- **PDF generation error:** Ensure WeasyPrint is properly installed

### Dependencies
- Flask 2.3.3+
- SQLAlchemy for database
- Pandas for Excel processing
- WeasyPrint for PDF generation
- Bootstrap 5.3.0 (CDN)
- Chart.js 3.9.1 (CDN)