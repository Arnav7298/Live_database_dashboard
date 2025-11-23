import dash
from dash import dcc, html, Input, Output, dash_table, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import sqlalchemy

# ----------------------------------------------------------------------------------
# SECTION 1: DATA INGESTION (REAL DATABASE)
# ----------------------------------------------------------------------------------

# CONNECTION STRING
db_uri = db_uri = 'postgresql://lumaxdev:lumaxdev@74.225.136.91:9832/lumaxdev'

try:
    engine = sqlalchemy.create_engine(db_uri)
    
    # SQL QUERY
    query = '''
        SELECT 
            e.id,
            e.name as employee_name,
            e.gender,
            d.name as department_name,
            j.name as job_title,
            rc.name as shift_name,
            rc.id as shift_id,
            pl.name as plant_line_name,
            pl.capacity as plant_line_capacity
        FROM hr_employee e
        LEFT JOIN hr_department d ON e.department_id = d.id
        LEFT JOIN hr_job j ON e.job_id = j.id
        LEFT JOIN resource_calendar rc ON e.resource_calendar_id = rc.id
        LEFT JOIN plant_line pl ON e.plant_line_id = pl.id
        WHERE e.gender IS NOT NULL 
    '''
    
    # Load data into Pandas
    df = pd.read_sql(query, engine)
    
    # Clean up missing values
    df['department_name'] = df['department_name'].fillna('Unknown Department')
    df['job_title'] = df['job_title'].fillna('Unknown Designation')
    df['shift_name'] = df['shift_name'].fillna('Unknown Shift')
    df['plant_line_name'] = df['plant_line_name'].fillna('Unassigned')
    df['plant_line_capacity'] = df['plant_line_capacity'].fillna(0)
    
    print("Data loaded successfully!")

except Exception as e:
    print(f"Error connecting to database: {e}")
    df = pd.DataFrame(columns=['id', 'employee_name', 'gender', 'department_name', 
                               'job_title', 'shift_name', 'shift_id', 
                               'plant_line_name', 'plant_line_capacity'])

# ----------------------------------------------------------------------------------
# SECTION 2: CALCULATE KPIS
# ----------------------------------------------------------------------------------

if not df.empty:
    total_employees = len(df)
    num_departments = df['department_name'].nunique()
    num_designations = df['job_title'].nunique()
    num_shifts = df['shift_name'].nunique()
else:
    total_employees = 0
    num_departments = 0
    num_designations = 0
    num_shifts = 0

def create_kpi_card(title, value, sub_text, color):
    return dbc.Card([
        dbc.CardBody([
            html.H4(title, className="card-title", style={"fontSize": "0.9rem", "color": "#666", "marginBottom": "5px"}),
            html.H2(value, className="card-text", style={"fontWeight": "bold", "color": color, "fontSize": "2rem"}),
            html.Small(sub_text, className="text-muted")
        ])
    ], className="shadow-sm mb-4 text-center h-100")

# ----------------------------------------------------------------------------------
# SECTION 3: DATA PROCESSING AND APP INITIALIZATION
# ----------------------------------------------------------------------------------

# *** THIS WAS THE MISSING LINE ***
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

def create_gap_graph(dataframe, group_col, capacity_col, title, y_label):
    if dataframe.empty:
        return px.bar(title="No Data")
        
    # 1. Calculate AVAILABLE (Actual Count of Employees)
    df_avail = dataframe.groupby(group_col).size().reset_index(name='Available')
    
    # 2. Calculate REQUIRED (Capacity)
    # Filter for unique lines so we don't sum capacity for every single employee row
    df_unique_lines = dataframe.drop_duplicates(subset=[group_col, 'plant_line_name'])
    
    # Safety filter: Only include lines that actually have a capacity requirement > 0
    df_unique_lines = df_unique_lines[df_unique_lines[capacity_col] > 0]
    
    df_req = df_unique_lines.groupby(group_col)[capacity_col].sum().reset_index(name='Required')
    
    # 3. Merge Data
    df_gap = pd.merge(df_avail, df_req, on=group_col, how='outer').fillna(0)
    
    # 4. Melt for Double Bar Graph
    df_melted = df_gap.melt(id_vars=group_col, value_vars=['Available', 'Required'], 
                            var_name='Type', value_name='Count')
    
    # 5. Create Graph
    fig = px.bar(
        df_melted, 
        x='Count', 
        y=group_col, 
        color='Type',
        barmode='group',
        orientation='h',
        title=title,
        # Standard Blue (Available) vs Red (Required)
        color_discrete_map={'Available': '#1E90FF', 'Required': '#FF4136'}, 
        labels={group_col: y_label, 'Count': 'Number of Employees'}
    )
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# Generate Figures
fig_gap_skill = create_gap_graph(df, 'plant_line_name', 'plant_line_capacity', 
                                'Required vs Available by Skills', 'Skill / Role')

# For Department Gap: we calculate requirement based on the skills (plant lines) linked to people in that dept
fig_gap_dept = create_gap_graph(df, 'department_name', 'plant_line_capacity', 
                               'Required vs Available by Department', 'Department')


# Existing Figures
if not df.empty:
    df_dept = df.groupby(['department_name', 'gender']).size().reset_index(name='count')
    fig_dept = px.bar(df_dept, x='department_name', y='count', color='gender', barmode='group',
                      title='Employees by Department', color_discrete_map={'female': '#FF69B4', 'male': '#1E90FF'})
    fig_dept.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

    df_job = df.groupby(['job_title']).size().reset_index(name='count')
    df_job = df_job.sort_values(by='count', ascending=True)
    fig_job = px.bar(df_job, x='count', y='job_title', orientation='h', title='Employees by Designation')
    fig_job.update_yaxes(title=None)
    fig_job.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

    target_shift_ids = [10, 17, 19]
    df_shift = df[df['shift_id'].isin(target_shift_ids)]
    df_shift_grouped = df_shift.groupby('shift_name').size().reset_index(name='count')
    fig_shift = px.pie(df_shift_grouped, values='count', names='shift_name', title='Employee Count by Shift')
    fig_shift.update_traces(textinfo='value', hoverinfo='label+percent')
    fig_shift.update_layout(paper_bgcolor='rgba(0,0,0,0)')
else:
    fig_dept = px.bar(title="No Data")
    fig_job = px.bar(title="No Data")
    fig_shift = px.pie(title="No Data")


# ----------------------------------------------------------------------------------
# SECTION 4: APP LAYOUT
# ----------------------------------------------------------------------------------

app.layout = dbc.Container([
    
    dbc.Row([dbc.Col(html.H1("Workforce Monitoring Dashboard", className="text-center my-4"), width=12)]),

    # KPI ROW
    dbc.Row([
        dbc.Col(create_kpi_card("Total Employees", str(total_employees), "Active Workforce", "#2C3E50"), width=6, md=3),
        dbc.Col(create_kpi_card("Total Departments", str(num_departments), "Operational Units", "#1E90FF"), width=6, md=3),
        dbc.Col(create_kpi_card("Total Designations", str(num_designations), "Unique Roles", "#27AE60"), width=6, md=3),
        dbc.Col(create_kpi_card("Total Shifts", str(num_shifts), "Active Schedules", "#E67E22"), width=6, md=3),
    ]),
    
    html.Hr(),

    # ROW 1
    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardHeader("Departmental Overview"), dbc.CardBody([dcc.Graph(id='gender-dept-graph', figure=fig_dept)])])], width=12, lg=6, className="mb-4"),
        dbc.Col([dbc.Card([dbc.CardHeader("Designation Overview"), dbc.CardBody([dcc.Graph(id='job-title-graph', figure=fig_job)])])], width=12, lg=6, className="mb-4"),
    ]),

    # ROW 2
    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardHeader("Shift Distribution"), dbc.CardBody([dcc.Graph(id='shift-pie-graph', figure=fig_shift)])])], width=12, lg=8, className="mb-4 mx-auto"),
    ]),

    html.Hr(),
    
    # ROW 3: GAP ANALYSIS
    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardHeader("Skill Gap Analysis (Plant Line)"), dbc.CardBody([dcc.Graph(id='gap-skill-graph', figure=fig_gap_skill)])])], width=12, lg=6, className="mb-4"),
        dbc.Col([dbc.Card([dbc.CardHeader("Department Gap Analysis"), dbc.CardBody([dcc.Graph(id='gap-dept-graph', figure=fig_gap_dept)])])], width=12, lg=6, className="mb-4"),
    ]),
    
    # DRILL DOWN ROW
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.Span("Drill Down: Employee Details", style={'float': 'left', 'marginTop': '5px'}),
                        html.Span(" (Use 'Export' button in table to download)", style={'float': 'right', 'fontSize': '0.8rem', 'color': '#666', 'marginTop': '8px'})
                    ])
                ]),
                dbc.CardBody([
                    html.Div(id='drill-down-output', children="Click on any chart element above to see details.")
                ])
            ])
        ], width=12)
    ])
], fluid=True, style={'backgroundColor': '#f8f9fa'})

# ----------------------------------------------------------------------------------
# SECTION 5: INTERACTIVITY
# ----------------------------------------------------------------------------------

@app.callback(
    Output('drill-down-output', 'children'),
    [Input('gender-dept-graph', 'clickData'),
     Input('job-title-graph', 'clickData'),
     Input('shift-pie-graph', 'clickData'),
     Input('gap-skill-graph', 'clickData'),
     Input('gap-dept-graph', 'clickData')]
)
def display_click_data(dept_click, job_click, shift_click, skill_click, gap_dept_click):
    ctx = callback_context
    if not ctx.triggered:
        return dbc.Alert("Click on a chart to view the employee list.", color="info")
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    final_list = pd.DataFrame()
    msg = ""

    if button_id == 'gender-dept-graph' and dept_click:
        point = dept_click['points'][0]
        final_list = df[(df['department_name'] == point['x']) & (df['gender'] == ('female' if point['curveNumber'] == 0 else 'male'))]
        msg = f"Showing employees in {point['x']}"

    elif button_id == 'job-title-graph' and job_click:
        final_list = df[df['job_title'] == job_click['points'][0]['y']]
        msg = f"Showing employees with designation: {job_click['points'][0]['y']}"

    elif button_id == 'shift-pie-graph' and shift_click:
        final_list = df[df['shift_name'] == shift_click['points'][0]['label']]
        msg = f"Showing employees in shift: {shift_click['points'][0]['label']}"

    elif button_id == 'gap-skill-graph' and skill_click:
        clicked_skill = skill_click['points'][0]['y']
        final_list = df[df['plant_line_name'] == clicked_skill]
        msg = f"Showing Available employees for Skill: {clicked_skill}"

    elif button_id == 'gap-dept-graph' and gap_dept_click:
        clicked_dept = gap_dept_click['points'][0]['y']
        final_list = df[df['department_name'] == clicked_dept]
        msg = f"Showing Available employees in Department: {clicked_dept}"

    if final_list.empty:
        return dbc.Alert("No employee data found (You may have clicked a 'Required' bar).", color="warning")

    display_cols = ['id', 'employee_name', 'department_name', 'job_title', 'shift_name', 'plant_line_name']
    
    table = dash_table.DataTable(
        data=final_list[display_cols].to_dict('records'),
        columns=[{"name": i, "id": i} for i in display_cols],
        style_cell={'textAlign': 'left', 'fontFamily': 'sans-serif'},
        style_header={'backgroundColor': '#2C3E50', 'color': 'white', 'fontWeight': 'bold'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}],
        page_size=10,
        export_format="csv",
        export_headers="display",
    )
    
    return html.Div([html.H5(msg, className="mb-3"), table])

if __name__ == '__main__':
    app.run(debug=True)

