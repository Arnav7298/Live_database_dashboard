import pandas as pd
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
from dash import html
import calendar

# ---------------------------------------------------------
# 1. DATABASE CONNECTION
# ---------------------------------------------------------
db_connection_str = 'postgresql://lumaxprod:lumaxprod@4.213.103.83:9832/lumax'

db_connection = create_engine(
    db_connection_str,
    pool_pre_ping=True,    
    pool_recycle=600     
)

# ---------------------------------------------------------
# 2. DROPDOWN HELPERS
# ---------------------------------------------------------

def get_plant_options():
    try:
        query = "SELECT id, location, plant_code FROM plant_plant"
        df = pd.read_sql(query, db_connection)
        return [{'label': f"{row['location']} ({row['plant_code']})", 'value': row['id']} for index, row in df.iterrows()]
    except:
        return []

def get_company_options():
    query = """
    SELECT DISTINCT e.company_id 
    FROM hr_attendance a
    JOIN hr_employee e ON a.employee_id = e.id
    ORDER BY e.company_id
    """
    try:
        df = pd.read_sql(query, db_connection)
        options = []
        for index, row in df.iterrows():
            cid = row['company_id']
            label = f"Company {cid}"
            if cid == 4: label = "LATL"
            if cid == 8: label = "LIL"
            options.append({'label': label, 'value': cid})
        return options
    except:
        return []

def get_emp_type_options():
    return [
        {'label': 'Employee', 'value': 'employee'},
        {'label': 'Contractor', 'value': 'contractor'}
    ]

# ---------------------------------------------------------
# 3. FORMATTING HELPERS
# ---------------------------------------------------------

def decimal_to_time_str(val):
    if pd.isna(val) or val == 0:
        return ""
    hours = int(val)
    minutes = int(round((val - hours) * 60))
    return f"{hours}h {minutes}m"

# ---------------------------------------------------------
# 4. COMMON SQL BUILDER
# ---------------------------------------------------------

def build_base_query(plant_id, company_id, emp_type, contractor_id=None, supervisor_id=None):
    conditions = ["e.active = true"] 
    joins = "LEFT JOIN hr_employee e ON a.employee_id = e.id"
    
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if emp_type: conditions.append(f"LOWER(e.employee_type) = LOWER('{emp_type}')")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    if supervisor_id: conditions.append(f"e.parent_id = {supervisor_id}")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return joins, where_clause

# ---------------------------------------------------------
# 5. SUPERVISOR KPI HELPER (UPDATED)
# ---------------------------------------------------------

def get_supervisor_counts(supervisor_id, selected_date, company_id=None, plant_id=None, contractor_id=None):
    """
    Returns ONLY 'Present' count for a supervisor, respecting global filters.
    Modified to remove the 'Total' count as per requirements.
    """
    if not supervisor_id: return "0"
    
    try:
        # Build Filter Conditions
        conds = [f"parent_id = {supervisor_id}", "active = true"]
        
        if company_id: conds.append(f"company_id = {company_id}")
        if plant_id: conds.append(f"plant_id = {plant_id}")
        if contractor_id: conds.append(f"contractor_id = {contractor_id}")
        
        where_sql = " AND ".join(conds)

        # NOTE: 'Total' query removed for optimization since it is no longer displayed.

        # Present Employees Query
        q_present = f"""
            SELECT COUNT(DISTINCT e.id) 
            FROM hr_attendance a 
            JOIN hr_employee e ON a.employee_id = e.id 
            WHERE {where_sql.replace('parent_id', 'e.parent_id').replace('company_id', 'e.company_id').replace('plant_id', 'e.plant_id').replace('contractor_id', 'e.contractor_id').replace('active', 'e.active')} 
            AND DATE(a.check_in) = '{selected_date}'
        """
        present_count = pd.read_sql(q_present, db_connection).iloc[0, 0]

        return str(present_count)
    except:
        return "0"

# ---------------------------------------------------------
# 6. DATE & MATH HELPERS
# ---------------------------------------------------------

def calculate_work_days(date_str):
    try:
        dt = pd.to_datetime(date_str)
        year = dt.year
        month = dt.month
        num_days = calendar.monthrange(year, month)[1]
        sundays = 0
        for day in range(1, num_days + 1):
            if calendar.weekday(year, month, day) == 6:
                sundays += 1
        return num_days - sundays
    except:
        return 30

# ---------------------------------------------------------
# 7. STYLING HELPERS
# ---------------------------------------------------------

def apply_minimalist_style(fig, title=None, height=None):
    fig.update_layout(
        title=dict(
            text=title, 
            font=dict(size=14, color="var(--text-main)"), 
            x=0, y=1
        ) if title else None,
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=30, b=40),
        height=height,
        autosize=True,
        font=dict(family="Inter, sans-serif", color="var(--text-main)"), 
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, 
            font=dict(color="var(--text-main)")
        )
    )
    grid_color = 'rgba(128, 128, 128, 0.2)' 
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=grid_color, zeroline=False, showline=False, showticklabels=True)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=grid_color, zeroline=False, showline=False, showticklabels=True)
    return fig

def render_info_tooltip(id_name, message, placement="auto"):
    return html.Span([
        html.I(className="fa-solid fa-circle-info ms-2 text-muted", id=id_name, style={"cursor": "pointer", "fontSize": "0.9rem", "opacity": "0.8"}),
        dbc.Tooltip(message, target=id_name, placement=placement, style={"fontSize": "0.85rem", "maxWidth": "250px"})
    ])

def create_user_status_widget(emp_name, contractor, current_date):
    contractor_display = contractor if contractor else "Internal / All Scope"
    name_display = emp_name if emp_name else "Unknown User"
    
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fa-solid fa-circle-user fa-xl text-primary me-3"), 
                        html.Div([
                            html.Div("Logged in as", className="small text-uppercase fw-bold", style={'fontSize': '0.7rem', 'opacity': '0.7'}),
                            html.Div(name_display, className="fw-bold", style={'fontSize': '1.1rem'})
                        ], className="d-flex flex-column")
                    ], className="d-flex align-items-center")
                ], width="auto", className="border-end pe-4 me-4"),
                
                dbc.Col([
                    html.Div([
                        html.I(className="fa-solid fa-building-shield fa-xl text-primary me-3"), 
                        html.Div([
                            html.Div("Contractor", className="small text-uppercase fw-bold", style={'fontSize': '0.7rem', 'opacity': '0.7'}),
                            html.Div(contractor_display, className="fw-bold", style={'fontSize': '1.1rem'})
                        ], className="d-flex flex-column")
                    ], className="d-flex align-items-center")
                ], width="auto", className="border-end pe-4 me-4"),

                dbc.Col([
                    html.Div([
                        html.I(className="fa-regular fa-calendar-check fa-xl text-primary me-3"), 
                        html.Div([
                            html.Div("Selected Date", className="small text-uppercase fw-bold", style={'fontSize': '0.7rem', 'opacity': '0.7'}),
                            html.Div(str(current_date), className="fw-bold", style={'fontSize': '1.1rem'})
                        ], className="d-flex flex-column")
                    ], className="d-flex align-items-center")
                ], width="auto")
            ], className="justify-content-center align-items-center g-0")
        ], className="p-2")
    ], className="mb-4 shadow-sm", style={"borderLeft": "5px solid var(--primary-color)"})
