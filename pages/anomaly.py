import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from utils import db_connection, create_user_status_widget, get_supervisor_counts

dash.register_page(__name__, path='/anomaly')

layout = dbc.Container([
    # Store for session data
    dcc.Store(id='anomaly-data-store'),

    # Header - Kept the "Anomaly" title
    html.H3([html.I(className="fa-solid fa-triangle-exclamation me-2"), "Data Quality & Anomaly Tracking"], className="mb-4 text-danger fw-bold"),

    # --- 1. MINI STATUS WIDGET ---
    html.Div(id='anomaly-status-widget'),

    # --- 2. CONTROLS ROW (Single Date + Supervisor KPI) ---
    dbc.Row([
        # SINGLE DATE PICKER (Requested Feature)
        dbc.Col([
            html.Label([html.I(className="fa-regular fa-calendar me-2"), "Select Date"], className="fw-bold small"),
            dcc.DatePickerSingle(
                id='anomaly-date', 
                date=date(2025, 11, 15), 
                min_date_allowed=date(2020, 1, 1),
                max_date_allowed=date(2030, 12, 31),
                display_format='Y-MM-DD',
                className="d-block w-100 shadow-sm"
            )
        ], width=4),

        # EMPLOYEES PRESENT WIDGET (Requested Feature)
        dbc.Col([
             dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H6("Employees Present", className="card-subtitle text-muted mb-1 small text-uppercase"),
                            html.H4(id="anomaly-kpi-supervisor-count", children="0 / 0", className="card-title text-primary fw-bold mb-0")
                        ], width=8),
                        dbc.Col([
                            html.I(className="fa-solid fa-people-group fa-2x text-black-50")
                        ], width=4, className="d-flex align-items-center justify-content-end")
                    ])
                ], className="p-2")
             ], className="shadow-sm border-0 h-100")
        ], width=4),

        # Spacer (or you can add Export buttons here if needed later)
        dbc.Col(width=4),

    ], className="mb-4 align-items-end"),

    html.Hr(), 

    # --- 3. ATTENDANCE ANOMALY TABLES (Driven by Single Date) ---
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader([html.I(className="fa-solid fa-user-slash me-2 text-danger"), "Missed Check-Out Details"], className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-missed', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader([html.I(className="fa-solid fa-clock me-2 text-warning"), "Multiple Check-In Details"], className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-multi', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-4"),

    # --- 4. MASTER DATA ANOMALY TABLES (Driven by Supervisor Scope) ---
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Skills", className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-skills', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Contractor ID", className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-contractor', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Salary Category", className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-desig', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Department", className="fw-bold border-bottom"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-dept', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-5"),

], fluid=True)

# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. WIDGET UPDATE
@callback(
    Output('anomaly-status-widget', 'children'), 
    [Input('user-context-store', 'data'),
     Input('anomaly-date', 'date')]
)
def update_anomaly_widget(user_data, selected_date):
    # --- GUARD CLAUSE ---
    if user_data is None: 
        return dash.no_update
    # --------------------
    
    emp_name = user_data.get('emp_name', 'Unknown')
    contractor = user_data.get('contractor_name', None)
    date_display = str(selected_date) if selected_date else "Select Date"
    
    return create_user_status_widget(emp_name, contractor, date_display)

# --- SUPERVISOR KPI CALLBACK ---
@callback(
    Output('anomaly-kpi-supervisor-count', 'children'), 
    [Input('anomaly-date', 'date'), Input('user-context-store', 'data')]
)
def update_md_supervisor_kpi(selected_date, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None: 
        return "0 / 0"
    # --------------------
    
    supervisor_id = user_data.get('empid')
    return get_supervisor_counts(supervisor_id, selected_date)

# 2. ATTENDANCE ANOMALIES (Missed Punch / Multi Punch)
@callback(
    [Output('tbl-missed', 'children'), Output('tbl-multi', 'children')],
    [Input('anomaly-date', 'date'),
     Input('user-context-store', 'data')]
)
def update_attendance_tables(selected_date, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None: 
        return html.Div("Loading..."), html.Div("Loading...")
    # --------------------

    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id')
    contractor_id = user_data.get('contractor_id')
    supervisor_id = user_data.get('empid') # NEW: Fetch Supervisor ID

    conditions = ["e.active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    
    # NEW: Filter by Supervisor
    if supervisor_id: conditions.append(f"e.parent_id = {supervisor_id}")
    
    # SINGLE DATE FILTER
    date_cond = f"AND DATE(a.check_in) = '{selected_date}'" if selected_date else "AND 1=0"
    join_sql = f"AND {' AND '.join(conditions)}"

    # Query 1: Missed Check-out (On selected date)
    q_missed = f"""
        SELECT DATE(a.check_in) as "Date", e.name as "Name", e.employee_code as "Employee Code" 
        FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE a.check_out IS NULL {date_cond} {join_sql}
        ORDER BY a.check_in DESC LIMIT 50
    """
    
    # Query 2: Multiple Check-ins (On selected date)
    q_multi = f"""
        SELECT DATE(a.check_in) as "Date", e.name as "Name", e.employee_code as "Employee Code", COUNT(*) as "Count"
        FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE 1=1 {date_cond} {join_sql} 
        GROUP BY a.employee_id, DATE(a.check_in), e.name, e.employee_code
        HAVING COUNT(*) > 1
        ORDER BY "Date" DESC LIMIT 50
    """

    def make_table(query):
        try:
            df = pd.read_sql(query, db_connection)
            if df.empty: return dbc.Alert("No anomalies found.", color="success")
            # Using simple Bootstrap table
            table = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, size='sm') 
            return table
        except Exception as e: return dbc.Alert(f"Error: {e}", color="danger")

    return make_table(q_missed), make_table(q_multi)

# 3. MASTER DATA ANOMALIES (Static, filtered by Supervisor)
@callback(
    [Output('tbl-skills', 'children'), Output('tbl-contractor', 'children'),
     Output('tbl-desig', 'children'), Output('tbl-dept', 'children')],
    [Input('user-context-store', 'data')]
)
def update_master_tables(user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return [html.Div("Loading...")] * 4
    # --------------------

    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id')
    contractor_id = user_data.get('contractor_id')
    supervisor_id = user_data.get('empid') # NEW: Fetch Supervisor ID

    conditions = ["active = true"] 
    if company_id: conditions.append(f"company_id = {company_id}")
    if plant_id: conditions.append(f"plant_id = {plant_id}")
    if contractor_id: conditions.append(f"contractor_id = {contractor_id}")
    
    # NEW: Filter by Supervisor
    if supervisor_id: conditions.append(f"parent_id = {supervisor_id}")

    where_base = "WHERE " + " AND ".join(conditions)

    def get_doj_style(doj_val):
        if pd.isna(doj_val): return {}
        doj_date = doj_val.date() if hasattr(doj_val, 'date') else doj_val
        diff_days = (date.today() - doj_date).days
        
        if diff_days <= 1: return {'color': 'white', 'fontWeight': 'bold', 'backgroundColor': '#28a745'} 
        elif diff_days <= 7: return {'color': '#fd7e14', 'fontWeight': 'bold'}
        else: return {'color': '#dc3545', 'fontWeight': 'bold'}

    def get_table(cond):
        query = f"SELECT create_date, name as \"Name\", employee_code as \"Employee Code\" FROM hr_employee {where_base} AND {cond} ORDER BY create_date DESC LIMIT 50"
        try:
            df = pd.read_sql(query, db_connection)
            if df.empty: return dbc.Alert("Clean Data!", color="success")
            rows = []
            for _, row in df.iterrows():
                style = get_doj_style(row['create_date'])
                date_str = row['create_date'].strftime('%Y-%m-%d') if pd.notnull(row['create_date']) else "N/A"
                rows.append(html.Tr([html.Td(date_str, style=style), html.Td(row['Name']), html.Td(row['Employee Code'])]))
            
            return dbc.Table([html.Thead(html.Tr([html.Th("DOJ"), html.Th("Name"), html.Th("Employee Code")])), html.Tbody(rows)], bordered=True, size='sm', hover=True)
        except: return dbc.Alert("Error", color="danger")

    return get_table("skills_status IS NULL"), get_table("contractor_id IS NULL"), get_table("job_id IS NULL"), get_table("department_id IS NULL")



