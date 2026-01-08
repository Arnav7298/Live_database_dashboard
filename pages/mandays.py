import dash
from dash import dcc, html, Input, Output, State, callback, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from fpdf import FPDF
import numpy as np
from utils import db_connection, render_info_tooltip, create_user_status_widget

dash.register_page(__name__, path='/mandays', name='Man Days')

layout = dbc.Container([
    dcc.Store(id='md-data-store'),
    dcc.Download(id="md-download-csv"),
    dcc.Download(id="md-download-pdf"),

    # Header
    html.H3([html.I(className="fa-solid fa-table-list me-2"), "Man Days Details"], className="mb-4 text-primary fw-bold"),

    # --- 1. MINI STATUS WIDGET ---
    html.Div(id='md-status-widget'),

    # --- 2. DATE FILTER ---
    dbc.Row([
        dbc.Col([
            html.Label([html.I(className="fa-regular fa-calendar me-2"), "Date Range"], className="fw-bold small"),
            dcc.DatePickerRange(id='md-date', start_date=date(2025, 11, 15), end_date=date(2025, 11, 30), className="d-block w-100 shadow-sm")
        ], width=4),
    ], className="mb-4"),

    # --- ACTION BUTTONS ---
    dbc.Row([
        dbc.Col(width=8),
        dbc.Col(dbc.Button([html.I(className="fa-solid fa-file-csv me-2"), "Export CSV"], id="md-btn-csv", color="success", size="sm", className="w-100 shadow-sm"), width=2),
        dbc.Col(dbc.Button([html.I(className="fa-solid fa-file-pdf me-2"), "Export PDF"], id="md-btn-pdf", color="danger", size="sm", className="w-100 shadow-sm"), width=2),
    ], className="mb-3"),

    # --- DATA TABLE CARD ---
    dbc.Card([
        dbc.CardBody([
            dcc.Loading(html.Div(id='mandays-table-container', style={'overflowX': 'auto'}))
        ])
    ], className="shadow-sm border-0")

], fluid=True)


# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. WIDGET UPDATE
@callback(Output('md-status-widget', 'children'), Input('user-context-store', 'data'))
def update_mandays_widget(user_data):
    if not user_data: return dash.no_update
    empid = user_data.get('empid', 'Unknown')
    contractor = user_data.get('contractor_name', None)
    return create_user_status_widget(empid, contractor)

# 2. GENERATE TABLE
@callback(
    [Output('mandays-table-container', 'children'),
     Output('md-data-store', 'data')],
    [Input('md-date', 'start_date'), Input('md-date', 'end_date'),
     Input('user-context-store', 'data')] 
)
def update_table(start_date, end_date, user_data):
    plant_id = user_data.get('plant_id') if user_data else None
    company_id = user_data.get('company_id') if user_data else None
    contractor_id = user_data.get('contractor_id') if user_data else None

    conds = ["e.active = true"]
    if company_id: conds.append(f"e.company_id = {company_id}")
    if plant_id: conds.append(f"e.plant_id = {plant_id}")
    if contractor_id: conds.append(f"e.contractor_id = {contractor_id}")
    
    date_cond = ""
    if start_date and end_date:
        date_cond = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'"

    where_sql = "WHERE " + " AND ".join(conds) if conds else "WHERE 1=1"

    query = f"""
    SELECT 
        s.name as "Shift",
        COALESCE(d.name, 'Unknown') as "Department",
        e.id as emp_id,
        s.hours_per_day as std_hours,
        EXTRACT(EPOCH FROM (a.check_out - a.check_in))/3600 as worked_hours
    FROM hr_attendance a
    JOIN hr_employee e ON a.employee_id = e.id
    JOIN resource_calendar s ON e.resource_calendar_id = s.id
    LEFT JOIN hr_department d ON e.department_id = d.id
    LEFT JOIN hr_job j ON e.job_id = j.id
    {where_sql} {date_cond} AND a.check_out IS NOT NULL
    """
    
    try:
        df = pd.read_sql(query, db_connection)
        
        if df.empty:
            return dbc.Alert("No data found for these filters.", color="warning"), []

        # LOGIC
        df['is_standard'] = df['worked_hours'] >= df['std_hours']
        df['is_early'] = df['worked_hours'] < df['std_hours']
        df['diff'] = df['worked_hours'] - df['std_hours']
        df['diff_floor'] = np.floor(df['diff'])
        
        df['is_extra'] = (df['diff'] > 0) & (df['diff'] <= 3.5) & (df['diff_floor'] >= 1)
        df['val_extra'] = np.where(df['is_extra'], df['diff_floor'], 0)

        df['good_raw'] = df['diff'] - 3.5
        df['good_floor'] = np.floor(df['good_raw'])
        df['is_good'] = df['good_raw'] > 0
        df['val_good'] = np.where(df['is_good'], df['good_floor'], 0)

        df['ot_raw'] = np.floor(df['diff'])
        df['val_ot'] = np.where(df['ot_raw'] > 0, df['ot_raw'], 0)

        grouped = df.groupby(['Shift', 'Department', 'std_hours']).agg(
            Total_Emp=('emp_id', 'nunique'),
            Std_Emp=('is_standard', 'sum'),
            Early_Emp=('is_early', 'sum'),
            Extra_Emp=('is_extra', 'sum'),
            Sum_Extra_Hrs=('val_extra', 'sum'),
            Good_Emp=('is_good', 'sum'),
            Sum_Good_Hrs=('val_good', 'sum'), 
            Sum_OT_Hrs=('val_ot', 'sum')
        ).reset_index()

        grouped['Extra_MD'] = (grouped['Sum_Extra_Hrs'] / grouped['std_hours']).round(2)
        grouped['Good_MD'] = (grouped['Sum_Good_Hrs'] / grouped['std_hours']).round(2)
        grouped['OT_MD'] = (grouped['Sum_OT_Hrs'] / grouped['std_hours']).round(2)
        
        grouped.sort_values(['Shift', 'Department'], inplace=True)

        table_header = [
            html.Tr([
                html.Th("Shift"), html.Th("Department"),
                html.Th("Total Emp"),
                html.Th("Std Hrs Emp"),
                html.Th("Early Exit"),
                html.Th("Extra Hrs Emp"),
                html.Th("Extra Hrs MD"),
                html.Th("Good Hrs Emp"),
                html.Th("Good Hrs MD"),
                html.Th("OT Man Days")
            ])
        ]

        table_rows = []
        for _, row in grouped.iterrows():
            # --- CLEANED UP ROWS (No Colors, just Data) ---
            table_rows.append(html.Tr([
                html.Td(row['Shift'], className="fw-bold"), # Kept bold, removed color
                html.Td(row['Department']),
                html.Td(row['Total_Emp']),
                html.Td(row['Std_Emp']),   # Removed text-success
                html.Td(row['Early_Emp']), # Removed text-warning
                html.Td(row['Extra_Emp']), # Removed text-danger
                html.Td(row['Extra_MD'], className="fw-bold"),
                html.Td(row['Good_Emp']),  # Removed text-primary
                html.Td(row['Good_MD'], className="fw-bold"),
                html.Td(row['OT_MD'], className="fw-bold") # Removed text-light
            ]))

        table = dbc.Table([html.Thead(table_header), html.Tbody(table_rows)], 
                          bordered=True, hover=True, striped=True, size='sm')
        
        return table, grouped.to_dict('records')

    except Exception as e:
        return dbc.Alert(f"Error processing data: {e}", color="danger"), []

@callback(Output("md-download-csv", "data"), Input("md-btn-csv", "n_clicks"), State("md-data-store", "data"), prevent_initial_call=True)
def download_csv(n, data):
    if not n or not data: return dash.no_update
    return dcc.send_data_frame(pd.DataFrame(data).to_csv, filename="mandays_report.csv", index=False)

@callback(Output("md-download-pdf", "data"), Input("md-btn-pdf", "n_clicks"), State("md-data-store", "data"), prevent_initial_call=True)
def download_pdf(n, data):
    if not n or not data: return dash.no_update
    df = pd.DataFrame(data)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Man Days Detailed Report", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", size=8)
    
    cols = ['Shift', 'Department', 'Total_Emp', 'Std_Emp', 'Early_Emp', 'Extra_Emp', 'Extra_MD', 'Good_Emp', 'Good_MD', 'OT_MD']
    col_w = [20, 50, 20, 20, 20, 20, 20, 20, 20, 20]
    
    for i, col in enumerate(cols):
        pdf.cell(col_w[i], 8, col[:12], border=1, align='C')
    pdf.ln()
    for _, row in df.iterrows():
        for i, col in enumerate(cols):
            val = str(row.get(col, '-'))
            pdf.cell(col_w[i], 8, val[:25], border=1, align='C')
        pdf.ln()
    def to_output(file_obj): pdf_string = pdf.output(dest='S'); file_obj.write(pdf_string.encode('latin-1'))
    return dcc.send_bytes(to_output, "mandays_report.pdf")
