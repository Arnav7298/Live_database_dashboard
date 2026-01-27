import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import urllib.parse
import pandas as pd
from utils import db_connection 

# 1. Add Fonts
FONT_INTER = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap"
FONT_AWESOME = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"

app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_stylesheets=[dbc.themes.BOOTSTRAP, FONT_AWESOME, FONT_INTER],
    suppress_callback_exceptions=True
)
server = app.server

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    
    # --- STORES ---
    dcc.Store(id='user-context-store', storage_type='session'),
    dcc.Store(id='theme-store', data='light'), 
    dcc.Store(id='global-date-store', storage_type='session'), # Preserved from local

    dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink([html.I(className="fa-solid fa-users me-2"), "Attendance"], href="/")),
            dbc.NavItem(dbc.NavLink([html.I(className="fa-solid fa-triangle-exclamation me-2"), "Anomaly"], href="/anomaly")),
            dbc.NavItem(dbc.NavLink([html.I(className="fa-solid fa-table-list me-2"), "Man Days"], href="/mandays")),
            
            # --- THEME SWITCH ---
            dbc.NavItem(
                html.Div([
                    html.I(className="fa-solid fa-sun me-2 text-warning"), 
                    dbc.Switch(id="theme-switch", value=False, className="d-inline-block align-middle"),
                    html.I(className="fa-solid fa-moon ms-2 text-secondary"), 
                ], className="d-flex align-items-center ms-3 me-3 p-2 rounded border border-light")
            ),
        ],
        brand=[html.I(className="fa-solid fa-chart-line me-2"), "HR Dashboard"],
        brand_href="/",
        color="primary", 
        dark=True,
        className="mb-0 shadow-sm"
    ),
    dash.page_container
], fluid=True)


# --- 1. THEME SWITCHER (Clientside) ---
app.clientside_callback(
    """
    function(value) {
        if (value) {
            document.documentElement.setAttribute('data-theme', 'dark');
            return 'dark';
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
            return 'light';
        }
    }
    """,
    Output('theme-store', 'data'),
    Input('theme-switch', 'value')
)

# --- 2. GLOBAL LOGIN CALLBACK ---
@app.callback(
    Output('user-context-store', 'data'),
    Input('url', 'search'),
    State('user-context-store', 'data')
)
def handle_login(search_str, current_data):
    target_id = None
    
    # Check URL for empid
    if search_str:
        try:
            parsed = urllib.parse.parse_qs(search_str.lstrip('?'))
            url_id = parsed.get('empid', [None])[0]
            if url_id: target_id = url_id
        except:
            pass

    # Fallback to Session
    if not target_id and current_data and current_data.get('empid'):
        target_id = current_data['empid']

    if not target_id: 
        return {'empid': None, 'emp_name': 'Guest', 'locked': True, 'contractor_name': 'Not Logged In'}

    try:
        query = f"""
        SELECT e.id, e.name, e.company_id, e.plant_id, e.contractor_id, c.contractor_name 
        FROM hr_employee e LEFT JOIN plant_contractor c ON e.contractor_id = c.id
        WHERE e.id = {target_id} AND e.active = true 
        """
        df = pd.read_sql(query, db_connection)
        
        if df.empty: 
            return {'empid': None, 'locked': True}
        
        row = df.iloc[0]
        c_name = row['contractor_name']
        display_name = c_name if pd.notnull(c_name) else "Internal / All"
        
        return {
            'empid': target_id,
            'emp_name': row['name'],
            'company_id': int(row['company_id']) if pd.notnull(row['company_id']) else None,
            'plant_id': int(row['plant_id']) if pd.notnull(row['plant_id']) else None,
            'contractor_id': int(row['contractor_id']) if pd.notnull(row['contractor_id']) else None,
            'contractor_name': display_name,
            'locked': False 
        }
    except Exception:
        return {'empid': None, 'locked': True}

# --- 3. AZURE PRODUCTION RUNNER ---
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)







