# app_dash_bootstrap.py
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
from data import get_data  # Import from new simulated data.py file
import dash_bootstrap_components as dbc
import pandas as pd

# Load data (now returns full simulated Dataframe)
df = get_data()

# Check if data was loaded
if df.empty:
    print("WARNING: No data was loaded. Check your data.py file.")

# --- Pre-calculate data for the "Required vs. Available" chart ---
# 1. Calculate "Available" (count of employees) by department
available_df = df.groupby('department_name')['employee_id'].count().reset_index()
available_df = available_df.rename(columns={'employee_id': 'count', 'department_name':'department'})
available_df['type'] = 'Available'

# 2. Calculate "Required" (sum of capacity) by department
# We can just sum the simulated capacity
required_df = df.groupby('department_name')['required_capacity'].sum().reset_index()
required_df = required_df.rename(columns={'required_capacity': 'count', 'department_name':'department'})
required_df['type'] = 'Required'

# 3. Combine them into one DataFrame for plotting
req_avail_df = pd.concat([available_df, required_df], ignore_index=True)
# --- End of pre-calculation ---


# Initialize the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # This exposes the internal Flask server for Render to build

# --- App Layout ---
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Live Employee Dashboard (Practice Mode)"), width=12, className="text-center my-4")),
    
    # --- Row 1: Master Chart (Department) and Shift Chart ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("Click a Department to Drill Down")),
                dbc.CardBody(
                    dcc.Graph(
                        id='dept-bar-chart',
                        figure=px.bar(
                            df.groupby('department_name')['employee_id'].count().reset_index(),
                            x='department_name', y='employee_id', title='Employee Count by Department'
                        ).update_layout(xaxis_title="Department", yaxis_title="Employee Count")
                    )
                )
            ])
        ], width=7),
        
        # THIS CHART WILL NOW WORK
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("Employee Count by Shift")),
                dbc.CardBody(
                    dcc.Graph(
                        id='shift-pie-chart',
                        figure=px.pie(
                            df['shift_name'].value_counts().reset_index(),
                            names='shift_name', values='count', title='Employees by Shift'
                        )
                    )
                )
            ])
        ], width=5)
    ]),
    
    # --- Row 2: Drill-Down Output Charts ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4(id='gender-chart-title')),
                dbc.CardBody(dcc.Graph(id='gender-chart'))
            ])
        ], width=6, className="mt-4"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4(id='designation-chart-title')),
                dbc.CardBody(dcc.Graph(id='designation-chart'))
            ])
        ], width=6, className="mt-4")
    ]),
    
    # --- Row 3: Required vs. Available Chart ---
    # THIS CHART WILL NOW WORK
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("Required vs. Available by Department")),
                dbc.CardBody(
                    dcc.Graph(
                        id='req-avail-chart',
                        figure=px.bar(
                            req_avail_df,
                            x='department', y='count', color='type',
                            barmode='group', title='Required vs. Available by Department'
                        ).update_layout(xaxis_title="Department", yaxis_title="Headcount")
                    )
                )
            ])
        ], width=12, className="mt-4")
    ])
    
], fluid=True)


# --- The Callback (This makes the drill-down work) ---
@app.callback(
    [Output('gender-chart', 'figure'),
     Output('designation-chart', 'figure'),
     Output('gender-chart-title', 'children'),
     Output('designation-chart-title', 'children')],
    [Input('dept-bar-chart', 'clickData')]
)
def update_drilldown_charts(clickData):
    
    if clickData is None:
        dff = df
        title_prefix = "Overall"
    else:
        # Filter based on the category name
        dept_name = clickData['points'][0]['x']
        dff = df[df['department_name'] == dept_name]
        title_prefix = f"In {dept_name}"
    
    # --- Chart 1: Gender ---
    gender_counts = dff['gender'].value_counts().reset_index()
    fig_gender = px.pie(
        gender_counts, 
        names='gender', 
        values='count',
    )
    gender_title = f"{title_prefix} Gender Distribution"

    # --- Chart 2: Designation ---
    designation_counts = dff['job_title'].value_counts().nlargest(15).reset_index()
    fig_designation = px.bar(
        designation_counts,
        x='job_title', y='count',
    ).update_layout(xaxis_title="Designation", yaxis_title="Employee Count")
    designation_title = f"{title_prefix} Designation Count (Top 15)"

    return fig_gender, fig_designation, gender_title, designation_title

# --- Run the App ---
if __name__ == '__main__':

    app.run(debug=True)
