import dash
from dash import dcc, html, Input, Output, State, callback, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from fpdf import FPDF  # <--- ADDED MISSING IMPORT
from utils import db_connection, get_company_options, get_plant_options, get_emp_type_options

# Register as a page
dash.register_page(__name__, path='/payroll')

# ---------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------
layout = dbc.Container([
    # Stores for this page
    dcc.Store(id='pay-drilldown-store'),
    dcc.Download(id="pay-download-csv"),
    dcc.Download(id="pay-download-pdf"),

    # 1. HEADER & FILTERS
    dbc.Row([
        dbc.Col([
            dbc.Row([
                dbc.Col([html.Label("Date Range"), dcc.DatePickerRange(id='pay-date', min_date_allowed=date(2020, 1, 1), max_date_allowed=date(2030, 12, 31), start_date=date(2025, 11, 15), end_date=date(2025, 11, 30), display_format='Y-MM-DD', className="d-block")], width=3),
                dbc.Col([html.Label("Company"), dcc.Dropdown(id='pay-comp', options=get_company_options(), placeholder="All", clearable=True)], width=3),
                dbc.Col([html.Label("Plant"), dcc.Dropdown(id='pay-plant', options=get_plant_options(), placeholder="All", clearable=True)], width=3),
                dbc.Col([html.Label("Type"), dcc.Dropdown(id='pay-type', options=get_emp_type_options(), placeholder="All", clearable=True)], width=3),
            ])
        ], width=12, className="align-self-center")
    ]),

    html.Hr(),

    # 2. GRAPHS (Now Side-by-Side)
    dbc.Row([
        # Graph 1: Department
        dbc.Col([
            html.H5("By Department", className="mb-3"),
            html.Small("Click a bar to view details", className="text-muted"),
            dcc.Loading(dcc.Graph(
                id='payroll-ot-graph', 
                config={'displayModeBar': False},
                style={'height': '400px'} # Fixed height to prevent stretching
            ))
        ], width=6),
        
        # Graph 2: Shift
        dbc.Col([
            html.H5("By Shift", className="mb-3"),
            html.Small("Click a bar to view details", className="text-muted"),
            dcc.Loading(dcc.Graph(
                id='payroll-shift-ot-graph', 
                config={'displayModeBar': False},
                style={'height': '400px'} # Fixed height
            ))
        ], width=6)
    ]),

    # 3. DRILL DOWN (Offcanvas Sidebar)
    dbc.Offcanvas(
        children=[
            dbc.Row([
                dbc.Col(dbc.Button("Export CSV", id="pay-btn-download", color="success", size="sm", className="w-100"), width=6),
                dbc.Col(dbc.Button("Export PDF", id="pay-btn-download-pdf", color="danger", size="sm", className="w-100"), width=6),
            ], className="mb-3"),
            html.Div(id='pay-table-container')
        ],
        id="pay-details-offcanvas",
        title="Payroll Details",
        is_open=False,
        placement="end",
        style={"width": "50%"}
    )

], fluid=True)


# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. LOGIN LOCKING
@callback(
    [Output('pay-comp', 'value'), Output('pay-comp', 'disabled'),
     Output('pay-plant', 'value'), Output('pay-plant', 'disabled')],
    Input('user-context-store', 'data')
)
def load_context(data):
    if data and data.get('locked'):
        return data['company_id'], True, data['plant_id'], True
    return None, False, None, False


# 2. DEPARTMENT GRAPH (ManDays)
@callback(
    Output('payroll-ot-graph', 'figure'),
    [Input('pay-date', 'start_date'), Input('pay-date', 'end_date'),
     Input('pay-plant', 'value'), Input('pay-comp', 'value')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE]
)
def update_payroll_graph(start_date, end_date, plant_id, company_id, user_data):
    # Filters
    date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'" if start_date and end_date else ""
    
    emp_conds = []
    if company_id: emp_conds.append(f"e.company_id = {company_id}")
    if plant_id: emp_conds.append(f"e.plant_id = {plant_id}")
    
    # [SECURITY UPDATE] Manually Check Contractor
    if user_data and user_data.get('contractor_id'):
        emp_conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    filter_where = "WHERE " + " AND ".join(emp_conds) if emp_conds else "WHERE 1=1"

    # Query
    query = f"""
    WITH daily_summary AS (
        SELECT a.employee_id, DATE(a.check_in) as work_date,
               SUM(EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600) as total_daily_hours
        FROM hr_attendance a
        WHERE a.check_out IS NOT NULL {date_cond}
        GROUP BY a.employee_id, DATE(a.check_in)
    ),
    unique_emp AS (SELECT DISTINCT ON (id) * FROM hr_employee ORDER BY id)
    SELECT d.name as dept_name,
           SUM(CASE WHEN ds.total_daily_hours > 8.5 THEN LEAST(ds.total_daily_hours - 8.5, 3.5) ELSE 0 END) as overtime_hours,
           SUM(CASE WHEN ds.total_daily_hours > 12 THEN ds.total_daily_hours - 12 ELSE 0 END) as good_hours
    FROM daily_summary ds
    JOIN unique_emp e ON ds.employee_id = e.id
    JOIN hr_department d ON e.department_id = d.id
    {filter_where}
    GROUP BY d.name ORDER BY d.name
    """
    try:
        df = pd.read_sql(query, db_connection)
        if df.empty: return go.Figure().update_layout(title="No Data")
        
        df['ot_md'] = (df['overtime_hours']/8.5).round(2)
        df['good_md'] = (df['good_hours']/8.5).round(2)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df['dept_name'], x=df['good_md'], name='Good Time (MD)', orientation='h', marker=dict(color='#0d6efd'), text=df['good_md'], textposition='auto'))
        fig.add_trace(go.Bar(y=df['dept_name'], x=df['ot_md'], name='Extra Hours (MD)', orientation='h', marker=dict(color='#198754'), text=df['ot_md'], textposition='auto'))
        
        fig.update_layout(
            barmode='group', 
            paper_bgcolor='white', 
            plot_bgcolor='rgba(240,240,240,0.5)', 
            xaxis_title="Total ManDays", 
            margin=dict(l=10, r=10, t=30, b=30),
            height=400, 
            bargap=0.1,
            autosize=False
        )
        return fig
    except Exception as e: return go.Figure().update_layout(title=f"Error: {e}")


# 3. SHIFT GRAPH (ManDays)
@callback(
    Output('payroll-shift-ot-graph', 'figure'),
    [Input('pay-date', 'start_date'), Input('pay-date', 'end_date'),
     Input('pay-plant', 'value'), Input('pay-comp', 'value'), Input('pay-type', 'value')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE]
)
def update_payroll_shift_graph(start_date, end_date, plant_id, company_id, emp_type, user_data):
    date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'" if start_date and end_date else ""
    
    emp_conds = []
    if company_id: emp_conds.append(f"e.company_id = {company_id}")
    if plant_id: emp_conds.append(f"e.plant_id = {plant_id}")
    if emp_type: emp_conds.append(f"LOWER(e.employee_type) = LOWER('{emp_type}')")
    
    # [SECURITY UPDATE] Manually Check Contractor
    if user_data and user_data.get('contractor_id'):
        emp_conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    filter_where = "WHERE " + " AND ".join(emp_conds) if emp_conds else "WHERE 1=1"

    query = f"""
    WITH daily_summary AS (
        SELECT a.employee_id, DATE(a.check_in) as work_date,
               SUM(EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600) as total_daily_hours
        FROM hr_attendance a
        WHERE a.check_out IS NOT NULL {date_cond}
        GROUP BY a.employee_id, DATE(a.check_in)
    ),
    unique_emp AS (SELECT DISTINCT ON (id) * FROM hr_employee ORDER BY id)
    SELECT s.name as shift_name,
           SUM(CASE WHEN ds.total_daily_hours > 8.5 THEN LEAST(ds.total_daily_hours - 8.5, 3.5) ELSE 0 END) as overtime_hours,
           SUM(CASE WHEN ds.total_daily_hours > 12 THEN ds.total_daily_hours - 12 ELSE 0 END) as good_hours
    FROM daily_summary ds
    JOIN unique_emp e ON ds.employee_id = e.id
    JOIN resource_calendar s ON e.resource_calendar_id = s.id
    {filter_where}
    GROUP BY s.name ORDER BY s.name
    """
    try:
        df = pd.read_sql(query, db_connection)
        if df.empty: return go.Figure().update_layout(title="No Data")
        
        df['ot_md'] = (df['overtime_hours']/8.5).round(2)
        df['good_md'] = (df['good_hours']/8.5).round(2)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df['shift_name'], x=df['good_md'], name='Good Time (MD)', orientation='h', marker=dict(color='#0d6efd'), text=df['good_md'], textposition='auto'))
        fig.add_trace(go.Bar(y=df['shift_name'], x=df['ot_md'], name='Extra Hours (MD)', orientation='h', marker=dict(color='#198754'), text=df['ot_md'], textposition='auto'))
        
        fig.update_layout(
            barmode='group', 
            paper_bgcolor='white', 
            plot_bgcolor='rgba(240,240,240,0.5)', 
            xaxis_title="Total ManDays", 
            margin=dict(l=10, r=10, t=30, b=30),
            height=400, 
            bargap=0.1,
            autosize=False
        )
        return fig
    except Exception as e: return go.Figure().update_layout(title=f"Error: {e}")


# 4. UNIFIED DRILL DOWN (NOW WITH OFFCANVAS)
@callback(
    [Output("pay-details-offcanvas", "is_open"), 
     Output("pay-table-container", "children"), 
     Output("pay-details-offcanvas", "title"),   
     Output("pay-drilldown-store", "data")],
     
    [Input("payroll-ot-graph", "clickData"),
     Input("payroll-shift-ot-graph", "clickData"),
     
     Input('pay-plant', 'value'), 
     Input('pay-comp', 'value'), 
     Input('pay-type', 'value')],
     
    [State('pay-date', 'start_date'),
     State('pay-date', 'end_date'),
     State('user-context-store', 'data')] # <--- [SECURITY UPDATE]
)
def payroll_drilldown(dept_click, shift_click, plant_id, company_id, emp_type, start_date, end_date, user_data):
    
    ctx = callback_context
    if not ctx.triggered: 
        return False, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if "pay-" in trigger_id and "graph" not in trigger_id:
         return False, dash.no_update, dash.no_update, dash.no_update

    # Base Filters
    emp_conds = []
    if company_id: emp_conds.append(f"e.company_id = {company_id}")
    if plant_id: emp_conds.append(f"e.plant_id = {plant_id}")
    if emp_type: emp_conds.append(f"LOWER(e.employee_type) = LOWER('{emp_type}')")
    
    # [SECURITY UPDATE] Manually Check Contractor
    if user_data and user_data.get('contractor_id'):
        emp_conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    where_base = "WHERE " + " AND ".join(emp_conds) if emp_conds else "WHERE 1=1"
    
    extra_cond = ""
    header_text = "Details"

    if trigger_id == "payroll-ot-graph" and dept_click:
        val = dept_click['points'][0]['y']
        extra_cond = f" AND d.name = '{val}'"
        header_text = f"Payroll: {val}"
        
    elif trigger_id == "payroll-shift-ot-graph" and shift_click:
        val = shift_click['points'][0]['y']
        extra_cond = f" AND s.name = '{val}'"
        header_text = f"Payroll: {val}"
    else:
        return False, dash.no_update, dash.no_update, dash.no_update

    if start_date and end_date:
        extra_cond += f" AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'"

    # DRILL DOWN SQL
    query = f"""
    SELECT DISTINCT 
        e.id as "ID", e.name as "Name", d.name as "Dept", s.name as "Shift",
        a.check_in as "In", a.check_out as "Out",
        FLOOR(EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600) || 'h ' || ROUND(((EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600) - FLOOR(EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600))*60) || 'm' as "Total",
        CASE WHEN EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600 > 8.5 THEN ROUND((LEAST((EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600)-8.5, 3.5))::numeric, 2) ELSE 0 END as "OT (Hrs)",
        CASE WHEN EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600 > 12 THEN ROUND(((EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600)-12)::numeric, 2) ELSE 0 END as "Good (Hrs)"
    FROM hr_attendance a
    LEFT JOIN hr_employee e ON a.employee_id = e.id
    LEFT JOIN hr_department d ON e.department_id = d.id
    LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id
    {where_base} {extra_cond}
    ORDER BY "In" DESC LIMIT 200
    """
    try:
        df = pd.read_sql(query, db_connection)
        if df.empty: return True, dbc.Alert("No Data", color="warning"), header_text, []
        
        df = df.astype(object)
        df.fillna("N/A", inplace=True)

        try:
            df['In'] = pd.to_datetime(df['In'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M').fillna("N/A")
            df['Out'] = pd.to_datetime(df['Out'], errors='coerce').dt.strftime('%H:%M').fillna("N/A")
        except: pass
        
        tbl = dbc.Table.from_dataframe(df, striped=True, bordered=True, size='sm')
        return True, tbl, header_text, df.to_dict('records')

    except Exception as e:
        return True, dbc.Alert(f"Error: {e}", color="danger"), "Error", []

# 5. CSV EXPORT
@callback(
    Output("pay-download-csv", "data"),
    Input("pay-btn-download", "n_clicks"),
    State("pay-drilldown-store", "data"),
    prevent_initial_call=True
)
def download_csv(n, data):
    if not n or not data: return dash.no_update
    return dcc.send_data_frame(pd.DataFrame(data).to_csv, filename="payroll_report.csv", index=False)

# 6. PDF EXPORT (ADDED BACK)
@callback(
    Output("pay-download-pdf", "data"),
    Input("pay-btn-download-pdf", "n_clicks"),
    State("pay-drilldown-store", "data"),
    prevent_initial_call=True
)
def download_pdf(n, data):
    if not n or not data: return dash.no_update
    df_export = pd.DataFrame(data)
    df_export.insert(0, "S.No", range(1, 1 + len(df_export)))
    df_export = df_export.astype(str)

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Payroll Details Report", ln=True, align='C')
    pdf.ln(5)

    # Columns: S.No, ID, Name, Dept, Shift, In, Out, Total, OT, Good
    # Total 10 columns. Total Width ~280mm
    col_widths = [10, 15, 40, 30, 25, 30, 30, 25, 20, 20] 
    
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(200, 220, 255)
    
    cols = df_export.columns.tolist()
    for i, col_name in enumerate(cols):
        w = col_widths[i] if i < len(col_widths) else 20
        text = (col_name[:15] + '..') if len(col_name) > 18 else col_name
        pdf.cell(w, 10, text, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font("Arial", size=8)
    pdf.set_fill_color(255, 255, 255)

    for index, row in df_export.iterrows():
        for i, item in enumerate(row):
            w = col_widths[i] if i < len(col_widths) else 20
            text = (item[:20] + '..') if len(item) > 22 else item
            pdf.cell(w, 8, text, border=1, align='C')
        pdf.ln()

    def to_output(file_obj):
        pdf_string = pdf.output(dest='S')
        file_obj.write(pdf_string.encode('latin-1'))

    return dcc.send_bytes(to_output, "payroll_report.pdf")
