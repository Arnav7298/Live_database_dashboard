# HR Analytics & Attendance Dashboard

A multi-page data visualization application built with **Python Dash** and **PostgreSQL**. This dashboard provides real-time insights into employee attendance, data anomalies, and man-day calculations, featuring role-based access control (Internal vs. Contractor scope).

##  Key Features

### 1. **Attendance Analytics (Home)**
* **Interactive KPIs:** Weekly attendance trends, department breakdowns, and demographic analysis (Gender, Skills, Shift).
* **Drill-Down Capability:** Click on any bar or data point to open a detailed side-panel view of specific employees (includes Employee Code).
* **Export:** Built-in PDF and CSV export functionality for all filtered data.

### 2. **Anomaly Tracking**
* **Data Quality Monitors:** Tracks "Missed Check-Outs," "Multiple Check-Ins," and Master Data gaps (missing Department, Skills, or Contractor IDs).
* **Visual Indicators:** "Traffic Light" color coding for Date of Joining (Green/White = New Joinee, Red = Older).
* **Smart Filtering:** Switch between Date Range and Single Date views.

### 3. **Man Days Reporting**
* **Shift Analysis:** Detailed breakdown of Standard Hours, Early Exits, and Extra/Good hours calculation.
* **Reporting:** Dedicated CSV and PDF generation for man-days reports.

### 4. **UI/UX & Theming**
* **Dual Theme System:** Instant toggle between **Light Mode** (Client Branding: White & Red) and **Dark Mode** (High Contrast) using CSS variables.
* **Responsive Design:** Built with Dash Bootstrap Components (DBC) and custom CSS for a mobile-responsive layout.

---

## Tech Stack

* **Frontend:** Dash, Dash Bootstrap Components, Plotly (Graphing), Custom CSS/JS.
* **Backend:** Python, Pandas, SQLAlchemy.
* **Database:** PostgreSQL (Schema includes: `hr_employee`, `hr_attendance`, `plant_contractor`, etc.).
* **Export Engine:** `fpdf` for PDF generation.

---

## Setup & Installation

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/your-username/hr-dashboard.git](https://github.com/your-username/hr-dashboard.git)
    cd hr-dashboard
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Database Configuration**
    * Update `utils.py` with the correct connection string or use environment variables.
    ```python
    # utils.py
    db_connection_str = 'postgresql://user:password@host:port/dbname'
    ```

4.  **Run the Application**
    ```bash
    python app.py
    ```
    The app will run at `http://127.0.0.1:8050/`.

---

## Authentication & Scope

The dashboard uses **URL-Parameter Based Authentication** to determine data scope (Internal vs. Contractor).

* **Usage:** Append `?empid=ID` to the base URL.
    * Example: `http://host:port/?empid=65925` loads data specifically for user 65925.
* **Logic:**
    1.  **Internal Employees:** See global data for their assigned Plant/Company.
    2.  **Contractors:** Data is strictly filtered to show only employees belonging to their `contractor_id`.
    3.  **Session Persistence:** The app retains the user session across page navigation.
    4.  **Access Denied:** If no ID is provided or the employee is marked `active=False`, the dashboard restricts data access.

---

## Project Structure

```text
├── assets/
│   └── custom.css       # Global styling & Dark Mode logic
├── pages/
│   ├── attendance.py    # Main Analytics Page (Home)
│   ├── anomaly.py       # Data Quality Page
│   └── mandays.py       # Man Days Reporting Page
├── app.py               # Application Entry Point & Login Logic
├── utils.py             # DB Connections, Shared Functions & Graph Styling
└── README.md            # Project Documentation
