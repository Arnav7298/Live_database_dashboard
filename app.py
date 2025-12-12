# This file sets up the app and handles the URL Login logic globally. 
# It stores the user's restricted Plant/Company in a dcc.Store so other pages can access it.

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import urllib.parse
from utils import db_connection 

app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
server = app.server

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='user-context-store', storage_type='session'),

    dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("Attendance", href="/")),
            dbc.NavItem(dbc.NavLink("Payroll", href="/payroll")),
            dbc.NavItem(dbc.NavLink("Anomaly Count", href="/anomaly")),
        ],
        brand="HR Dashboard",
        color="primary",
        dark=True,
        className="mb-4"
    ),
    dash.page_container
], fluid=True)

# --- GLOBAL LOGIN CALLBACK (UPDATED) ---
@app.callback(
    Output('user-context-store', 'data'),
    Input('url', 'search'),
    State('user-context-store', 'data')
)
def handle_login(search_str, current_data):
    if not search_str:
        return dash.no_update
    
    try:
        parsed = urllib.parse.parse_qs(search_str.lstrip('?'))
        # 1. CHANGE KEYWORD TO 'empid'
        user_id = parsed.get('empid', [None])[0]

        if user_id:
            import pandas as pd
            # 2. UPDATE QUERY TO FETCH CONTRACTOR_ID USING 'id'
            # Fetching contractor_id column from hr_employee
            query = f"SELECT company_id, plant_id, contractor_id FROM hr_employee WHERE id = {user_id}"
            df = pd.read_sql(query, db_connection)
            
            if not df.empty:
                return {
                    'empid': user_id, 
                    'company_id': int(df.iloc[0]['company_id']) if pd.notnull(df.iloc[0]['company_id']) else None,
                    'plant_id': int(df.iloc[0]['plant_id']) if pd.notnull(df.iloc[0]['plant_id']) else None,
                    # 3. STORE CONTRACTOR ID
                    'contractor_id': int(df.iloc[0]['contractor_id']) if pd.notnull(df.iloc[0]['contractor_id']) else None,
                    'locked': True
                }
        
        return dash.no_update

    except Exception as e:
        print(f"Login Error: {e}")
        return dash.no_update

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)


