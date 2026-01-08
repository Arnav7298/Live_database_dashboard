import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date, timedelta
from utils import db_connection, create_user_status_widget

dash.register_page(__name__, path='/anomaly')

layout = dbc.Container([
    # Header uses Red (text-danger) - kept as is since client wants Red focus
    html.H3([html.I(className="fa-solid fa-triangle-exclamation me-2"), "Data Quality & Anomaly Tracking"], className="mb-4 text-danger fw-bold"),

    # --- MINI STATUS WIDGET ---
    html.Div(id='anom-status-widget'),

    # --- CONTROL ROW: Date Filter + Total Present KPI ---
    dbc.Row([
        # 1. Date Filter Section
        dbc.Col([
            # Removed 'text-light' so label is dark in light mode
            html.Label([html.I(className="fa-regular fa-calendar-days me-2"), "Date Filter"], className="fw-bold small"),
            dbc.Row([
                dbc.Col(
                    dcc.RadioItems(
                        id='date-mode-radio',
                        options=[{'label': ' Range', 'value': 'range'}, {'label': ' Single', 'value': 'single'}],
                        value='range',
                        inline=True,
                        inputStyle={"margin-right": "5px"},
                        labelStyle={"margin-right": "10px", "fontSize": "0.85rem"} # Removed hardcoded color
                    ), width=12, className="mb-2"
                )
            ]),
            html.Div(id='div-date-range', children=[
                dcc.DatePickerRange(id='anom-date', start_date=date(2025, 11, 15), end_date=date(2025, 11, 30), className="d-block w-100 shadow-sm")
            ]),
            html.Div(id='div-date-single', style={'display': 'none'}, children=[
                dcc.DatePickerSingle(id='anom-date-single', date=date(2025, 11, 15), className="d-block w-100 shadow-sm")
            ])
        ], width=5, className="border-end pe-4"), # Removed 'border-secondary' to let theme handle border color

        # 2. Total Present KPI (Compact Widget)
        dbc.Col([
            # Removed color="dark", inverse=True. Changed to shadow-sm.
            dbc.Card(dbc.CardBody([
                html.Div([
                    html.Div([
                        # FIX: Removed 'text-muted' so it turns White in Dark Mode. Added opacity for style.
                        html.H6("Total Present", className="small text-uppercase mb-1", style={'opacity': '0.7'}), 
                        
                        # Removed 'text-light' so it adapts to theme
                        html.H3("0", id="kpi-present", className="fw-bold m-0")
                    ]),
                    html.Div(
                        # Changed text-info to text-primary (Client Red)
                        html.I(className="fa-solid fa-users fa-2x text-primary opacity-50"),
                        className="ms-auto"
                    )
                ], className="d-flex align-items-center")
            ]), className="shadow-sm border-0 h-100")
        ], width=3, className="ps-4"),

        # Spacer
        dbc.Col(width=4)

    ], className="mb-4 align-items-end"),

    html.Hr(), # Removed className="border-secondary" to let theme control it

    # 3. ATTENDANCE ANOMALY TABLES
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

    # 4. MASTER DATA ANOMALY TABLES
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
# CALLBACKS (Unchanged)
# ---------------------------------------------------------

@callback(Output('anom-status-widget', 'children'), Input('user-context-store', 'data'))
def update_anomaly_widget(user_data):
    if not user_data: return dash.no_update
    empid = user_data.get('empid', 'Unknown')
    contractor = user_data.get('contractor_name', None)
    return create_user_status_widget(empid, contractor)

@callback([Output('div-date-range', 'style'), Output('div-date-single', 'style')], Input('date-mode-radio', 'value'))
def toggle_date_mode(mode):
    if mode == 'single': return {'display': 'none'}, {'display': 'block'}
    return {'display': 'block'}, {'display': 'none'}

@callback(
    Output("kpi-present", "children"),
    [Input('anom-date', 'start_date'), Input('anom-date', 'end_date'),
     Input('anom-date-single', 'date'), Input('date-mode-radio', 'value'),
     Input('user-context-store', 'data')]
)
def update_kpi_present(start_range, end_range, single_date, mode, user_data):
    plant_id = user_data.get('plant_id') if user_data else None
    company_id = user_data.get('company_id') if user_data else None
    contractor_id = user_data.get('contractor_id') if user_data else None

    start_date = single_date if mode == 'single' else start_range
    end_date = single_date if mode == 'single' else end_range

    conditions = ["active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    
    date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'" if start_date and end_date else ""
    join_sql = f"AND {' AND '.join(conditions)}"
    
    q_present = f"SELECT COUNT(DISTINCT a.employee_id) FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id WHERE 1=1 {date_cond} {join_sql}"

    try:
        present = pd.read_sql(q_present, db_connection).iloc[0, 0]
        return str(present)
    except: return "0"

@callback(
    [Output('tbl-missed', 'children'), Output('tbl-multi', 'children')],
    [Input('anom-date', 'start_date'), Input('anom-date', 'end_date'),
     Input('anom-date-single', 'date'), Input('date-mode-radio', 'value'),
     Input('user-context-store', 'data')]
)
def update_attendance_tables(start_range, end_range, single_date, mode, user_data):
    plant_id = user_data.get('plant_id') if user_data else None
    company_id = user_data.get('company_id') if user_data else None
    contractor_id = user_data.get('contractor_id') if user_data else None

    start_date = single_date if mode == 'single' else start_range
    end_date = single_date if mode == 'single' else end_range

    conditions = ["active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    
    date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'" if start_date and end_date else ""
    join_sql = f"AND {' AND '.join(conditions)}"

    q_missed = f"""
        SELECT DATE(a.check_in) as "Date", e.name as "Name", e.employee_code as "Employee Code" 
        FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE a.check_out IS NULL {date_cond} {join_sql}
        ORDER BY a.check_in DESC LIMIT 50
    """
    
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
            
            # Removed color="dark" -> Now listens to theme
            table = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, size='sm') 
            return table
        except Exception as e: return dbc.Alert(f"Error: {e}", color="danger")

    return make_table(q_missed), make_table(q_multi)

@callback(
    [Output('tbl-skills', 'children'), Output('tbl-contractor', 'children'),
     Output('tbl-desig', 'children'), Output('tbl-dept', 'children')],
    [Input('user-context-store', 'data')]
)
def update_master_tables(user_data):
    plant_id = user_data.get('plant_id') if user_data else None
    company_id = user_data.get('company_id') if user_data else None
    contractor_id = user_data.get('contractor_id') if user_data else None

    conditions = ["active = true"] 
    if company_id: conditions.append(f"company_id = {company_id}")
    if plant_id: conditions.append(f"plant_id = {plant_id}")
    if contractor_id: conditions.append(f"contractor_id = {contractor_id}")

    where_base = "WHERE " + " AND ".join(conditions)

    def get_doj_style(doj_val):
        if pd.isna(doj_val): return {}
        doj_date = doj_val.date() if hasattr(doj_val, 'date') else doj_val
        diff_days = (date.today() - doj_date).days
        
        # NOTE: Colors here (white/orange/red) are specific indicators, 
        # so we keep them hardcoded as they represent data status, not theme.
        if diff_days <= 1: return {'color': 'white', 'fontWeight': 'bold', 'backgroundColor': '#28a745'} # Green bg for new joins visibility
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
            
            # Removed color="dark" -> Now listens to theme
            return dbc.Table([html.Thead(html.Tr([html.Th("DOJ"), html.Th("Name"), html.Th("Employee Code")])), html.Tbody(rows)], bordered=True, size='sm', hover=True)
        except: return dbc.Alert("Error", color="danger")

    return get_table("skills_status IS NULL"), get_table("contractor_id IS NULL"), get_table("job_id IS NULL"), get_table("department_id IS NULL")

