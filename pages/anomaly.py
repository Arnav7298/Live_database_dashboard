import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from utils import db_connection, get_company_options, get_plant_options

dash.register_page(__name__, path='/anomaly')

# ---------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------
layout = dbc.Container([
    
    html.H3("Data Quality & Anomaly Tracking", className="mb-4 text-danger"),

    # 1. KPI ROW
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H6("Total Present", className="text-muted"), html.H3("0", id="kpi-present", className="text-primary")]), className="shadow-sm"), width=4),
        dbc.Col(dbc.Card(dbc.CardBody([html.H6("Missed Check-Out", className="text-muted"), html.H3("0", id="kpi-missed", className="text-danger")]), className="shadow-sm"), width=4),
        dbc.Col(dbc.Card(dbc.CardBody([html.H6("Multiple Punches", className="text-muted"), html.H3("0", id="kpi-multi", className="text-warning")]), className="shadow-sm"), width=4),
    ], className="mb-4"),

    # 2. FILTERS
    dbc.Row([
        # --- DATE SECTION START ---
        dbc.Col([
            dbc.Row([
                dbc.Col([html.Label("Filter Mode:")], width=4, className="align-self-center"),
                dbc.Col([
                    dcc.RadioItems(
                        id='date-mode-radio',
                        options=[{'label': ' Range', 'value': 'range'}, {'label': ' Single', 'value': 'single'}],
                        value='range',
                        inline=True,
                        inputStyle={"margin-right": "5px", "margin-left": "10px"}
                    )
                ], width=8)
            ], className="mb-1"),
            
            # Container for Range Picker (Visible by default)
            html.Div(id='div-date-range', children=[
                dcc.DatePickerRange(
                    id='anom-date', 
                    min_date_allowed=date(2020, 1, 1), max_date_allowed=date(2030, 12, 31), 
                    start_date=date(2025, 11, 15), end_date=date(2025, 11, 30), 
                    display_format='Y-MM-DD', className="d-block"
                )
            ]),

            # Container for Single Picker (Hidden by default)
            html.Div(id='div-date-single', style={'display': 'none'}, children=[
                dcc.DatePickerSingle(
                    id='anom-date-single',
                    min_date_allowed=date(2020, 1, 1), max_date_allowed=date(2030, 12, 31),
                    date=date(2025, 11, 15),
                    display_format='Y-MM-DD', className="d-block", style={'width': '100%'}
                )
            ])
        ], width=4),
        # --- DATE SECTION END ---

        dbc.Col([html.Label("Company"), dcc.Dropdown(id='anom-comp', options=get_company_options(), placeholder="All Companies", clearable=True)], width=4),
        dbc.Col([html.Label("Plant"), dcc.Dropdown(id='anom-plant', options=get_plant_options(), placeholder="All Plants", clearable=True)], width=4),
    ], className="mb-4"),

    html.Hr(),

    # 3. ANOMALY TABLES - ROW 1
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Skills"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-skills', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], color="light", outline=True), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Contractor ID"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-contractor', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], color="light", outline=True), width=6),
    ], className="mb-4"),

    # 4. ANOMALY TABLES - ROW 2
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Salary Category"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-desig', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], color="light", outline=True), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Department"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-dept', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], color="light", outline=True), width=6),
    ]),

], fluid=True)


# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. LOGIN LOCKING
@callback(
    [Output('anom-comp', 'value'), Output('anom-comp', 'disabled'),
     Output('anom-plant', 'value'), Output('anom-plant', 'disabled')],
    Input('user-context-store', 'data')
)
def load_context(data):
    if data and data.get('locked'):
        return data['company_id'], True, data['plant_id'], True
    return None, False, None, False

# 2. TOGGLE DATE PICKERS
@callback(
    [Output('div-date-range', 'style'), Output('div-date-single', 'style')],
    Input('date-mode-radio', 'value')
)
def toggle_date_mode(mode):
    if mode == 'single':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'block'}, {'display': 'none'}


# 3. UPDATE KPIs (SECURE)
@callback(
    [Output("kpi-present", "children"),
     Output("kpi-missed", "children"),
     Output("kpi-multi", "children")],
    [Input('anom-date', 'start_date'),
     Input('anom-date', 'end_date'),
     Input('anom-date-single', 'date'),
     Input('date-mode-radio', 'value'),
     Input('anom-plant', 'value'), 
     Input('anom-comp', 'value')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_kpis(start_range, end_range, single_date, mode, plant_id, company_id, user_data):
    # Date Logic
    start_date = start_range
    end_date = end_range
    if mode == 'single':
        start_date = single_date
        end_date = single_date

    conditions = ["active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    
    # [SECURITY UPDATE] Manually Check Contractor
    if user_data and user_data.get('contractor_id'):
        conditions.append(f"e.contractor_id = {user_data['contractor_id']}")
    
    date_cond = ""
    if start_date and end_date:
        date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'"

    join_sql = f"AND {' AND '.join(conditions)}"
    
    q_present = f"SELECT COUNT(DISTINCT a.employee_id) FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id WHERE 1=1 {date_cond} {join_sql}"
    q_missed = f"SELECT COUNT(*) FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id WHERE a.check_out IS NULL {date_cond} {join_sql}"
    q_multi = f"""
    SELECT COUNT(*) FROM (
        SELECT a.employee_id FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE 1=1 {date_cond} {join_sql} 
        GROUP BY a.employee_id, DATE(a.check_in) HAVING COUNT(*) > 1
    ) as sub
    """

    try:
        present = pd.read_sql(q_present, db_connection).iloc[0, 0]
        missed = pd.read_sql(q_missed, db_connection).iloc[0, 0]
        multi = pd.read_sql(q_multi, db_connection).iloc[0, 0]
        return str(present), str(missed), str(multi)
    except:
        return "0", "0", "0"


# 4. ANOMALY TABLES (SECURE)
@callback(
    [Output('tbl-skills', 'children'), Output('tbl-contractor', 'children'),
     Output('tbl-desig', 'children'), Output('tbl-dept', 'children')],
    [Input('anom-comp', 'value'), Input('anom-plant', 'value')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_anomaly_tables(company_id, plant_id, user_data):
    conditions = ["active = true"] 
    if company_id: conditions.append(f"company_id = {company_id}")
    if plant_id: conditions.append(f"plant_id = {plant_id}")
    
    # [SECURITY UPDATE] Manually Check Contractor
    # Note: Tables query 'hr_employee' directly, so we use 'contractor_id' (no 'e.' prefix needed usually, but safe to omit prefix if single table)
    if user_data and user_data.get('contractor_id'):
        conditions.append(f"contractor_id = {user_data['contractor_id']}")

    where_base = "WHERE " + " AND ".join(conditions)

    def get_doj_style(doj_date):
        if pd.isna(doj_date): return {}
        d = doj_date.date() if hasattr(doj_date, 'date') else doj_date
        days = (date.today() - d).days
        if days <= 7: return {'backgroundColor': '#ffadad', 'color': 'black', 'fontWeight': 'bold'}
        elif days <= 14: return {'backgroundColor': '#ffd6a5', 'color': 'black'}
        elif days <= 21: return {'backgroundColor': '#fdffb6', 'color': 'black'}
        else: return {'backgroundColor': '#caffbf', 'color': 'black'}

    def get_table(cond):
        query = f"SELECT create_date, name as \"Name\", employee_code as \"Code\" FROM hr_employee {where_base} AND {cond} ORDER BY create_date DESC LIMIT 50"
        try:
            df = pd.read_sql(query, db_connection)
            if df.empty: return dbc.Alert("Clean Data!", color="success")
            rows = []
            for _, row in df.iterrows():
                rows.append(html.Tr([
                    html.Td(row['create_date'].strftime('%Y-%m-%d') if pd.notnull(row['create_date']) else "N/A", style=get_doj_style(row['create_date'])),
                    html.Td(row['Name']), html.Td(row['Code'])
                ]))
            return dbc.Table([html.Thead(html.Tr([html.Th("DOJ"), html.Th("Name"), html.Th("Code")])), html.Tbody(rows)], bordered=True, size='sm', hover=True)
        except: return dbc.Alert("Error", color="danger")

    return get_table("skills_status IS NULL"), get_table("contractor_id IS NULL"), get_table("designation IS NULL"), get_table("department_id IS NULL")
