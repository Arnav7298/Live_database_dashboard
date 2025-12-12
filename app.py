# This file sets up the app and handles the URL Login logic globally. 
# It stores the user's restricted Plant/Company in a dcc.Store so other pages can access it.

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import urllib.parse
from utils import db_connection # Import DB to check user ID

# Initialize App with Multi-Page Support
app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True  # <--- ADD THIS
)
server = app.server

app.layout = dbc.Container([
    # 1. URL Listener & Session Storage
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='user-context-store', storage_type='session'), # Stores login info

    # 2. Navigation Bar
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

    # 3. Page Content Container
    dash.page_container

], fluid=True)

# Reads URL ?uid=66055 and stores the user context
# --- GLOBAL LOGIN CALLBACK (FIXED FOR PERSISTENCE) ---
@app.callback(
    Output('user-context-store', 'data'),
    Input('url', 'search'),
    State('user-context-store', 'data')  # Access existing session data
)
def handle_login(search_str, current_data):
    # Scenario 1: No query string (e.g., User clicked "Payroll" link)
    # ACTION: Do NOT clear the store. Return no_update to keep existing login.
    if not search_str:
        return dash.no_update
    
    try:
        # Parse URL parameters
        parsed = urllib.parse.parse_qs(search_str.lstrip('?'))
        user_id = parsed.get('uid', [None])[0]

        # Scenario 2: URL has ?uid=... (User logs in or refreshes with ID)
        if user_id:
            # Query DB for context
            import pandas as pd
            query = f"SELECT company_id, plant_id FROM hr_employee WHERE id = {user_id}"
            df = pd.read_sql(query, db_connection)
            
            if not df.empty:
                # Save new context to Session Store
                return {
                    'uid': user_id, 
                    'company_id': int(df.iloc[0]['company_id']) if pd.notnull(df.iloc[0]['company_id']) else None,
                    'plant_id': int(df.iloc[0]['plant_id']) if pd.notnull(df.iloc[0]['plant_id']) else None,
                    'locked': True
                }
        
        # Scenario 3: URL has other params but no UID
        # ACTION: Keep existing session.
        return dash.no_update

    except Exception as e:
        print(f"Login Error: {e}")
        return dash.no_update

if __name__ == '__main__':
    app.run(debug=True)

