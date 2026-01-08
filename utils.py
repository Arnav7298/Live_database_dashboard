import pandas as pd
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
from dash import html
import calendar

# ---------------------------------------------------------
# 1. DATABASE CONNECTION
# ---------------------------------------------------------
db_connection_str = 'postgresql://lumaxuat:lumaxuat@4.247.149.0:9832/lumaxuat'
db_connection = create_engine(db_connection_str)

# ---------------------------------------------------------
# 2. DROPDOWN HELPERS
# ---------------------------------------------------------

def get_plant_options():
    try:
        query = "SELECT id, location, plant_code FROM plant_plant"
        df = pd.read_sql(query, db_connection)
        return [{'label': f"{row['location']} ({row['plant_code']})", 'value': row['id']} for index, row in df.iterrows()]
    except:
        return []

def get_company_options():
    query = """
    SELECT DISTINCT e.company_id 
    FROM hr_attendance a
    JOIN hr_employee e ON a.employee_id = e.id
    ORDER BY e.company_id
    """
    try:
        df = pd.read_sql(query, db_connection)
        options = []
        for index, row in df.iterrows():
            cid = row['company_id']
            label = f"Company {cid}"
            if cid == 4: label = "LATL"
            if cid == 8: label = "LIL"
            options.append({'label': label, 'value': cid})
        return options
    except:
        return []

def get_emp_type_options():
    return [
        {'label': 'Employee', 'value': 'employee'},
        {'label': 'Contractor', 'value': 'contractor'}
    ]

# ---------------------------------------------------------
# 3. FORMATTING HELPERS
# ---------------------------------------------------------

def decimal_to_time_str(val):
    if pd.isna(val) or val == 0:
        return ""
    hours = int(val)
    minutes = int(round((val - hours) * 60))
    return f"{hours}h {minutes}m"

# ---------------------------------------------------------
# 4. COMMON SQL BUILDER
# ---------------------------------------------------------

def build_base_query(plant_id, company_id, emp_type, contractor_id=None):
    """
    Constructs standard WHERE clauses.
    NOW INCLUDES: Global 'Active' Employee Check.
    """
    conditions = ["e.active = true"] 
    joins = "LEFT JOIN hr_employee e ON a.employee_id = e.id"
    
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if emp_type: conditions.append(f"LOWER(e.employee_type) = LOWER('{emp_type}')")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return joins, where_clause

# ---------------------------------------------------------
# 5. DATE & MATH HELPERS
# ---------------------------------------------------------

def calculate_work_days(date_str):
    try:
        dt = pd.to_datetime(date_str)
        year = dt.year
        month = dt.month
        num_days = calendar.monthrange(year, month)[1]
        sundays = 0
        for day in range(1, num_days + 1):
            if calendar.weekday(year, month, day) == 6:
                sundays += 1
        return num_days - sundays
    except:
        return 30

# ---------------------------------------------------------
# 6. STYLING HELPERS (Theme Adaptive)
# ---------------------------------------------------------

def apply_minimalist_style(fig, title=None, height=None):
    """
    Applies a THEME-ADAPTIVE style using CSS Variables.
    This allows graphs to automatically switch between Light (Black Text) and Dark (White Text) modes.
    """
    fig.update_layout(
        # Use CSS Variable for Text Color (Magic happens here)
        title=dict(
            text=title, 
            font=dict(size=14, color="var(--text-main)"), 
            x=0, y=1
        ) if title else None,
        
        # Transparent Backgrounds (Let CSS Body/Card color show through)
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        
        margin=dict(l=40, r=20, t=30, b=40),
        height=height,
        autosize=True,
        
        # Use CSS Variable for Global Font
        font=dict(family="Inter, sans-serif", color="var(--text-main)"), 
        
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, 
            font=dict(color="var(--text-main)")
        )
    )
    
    # Gridlines use a very subtle neutral color that works on both White and Black backgrounds
    grid_color = 'rgba(128, 128, 128, 0.2)' 
    
    fig.update_xaxes(
        showgrid=True, gridwidth=1, gridcolor=grid_color,
        zeroline=False, showline=False, showticklabels=True
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=grid_color,
        zeroline=False, showline=False, showticklabels=True
    )
    
    return fig

def render_info_tooltip(id_name, message, placement="auto"):
    """
    Creates a FontAwesome info icon with a Bootstrap Tooltip.
    Uses 'text-muted' to adapt to both themes nicely.
    """
    return html.Span([
        html.I(
            className="fa-solid fa-circle-info ms-2 text-muted", 
            id=id_name, 
            style={"cursor": "pointer", "fontSize": "0.9rem", "opacity": "0.8"}
        ),
        dbc.Tooltip(
            message,
            target=id_name,
            placement=placement,
            style={"fontSize": "0.85rem", "maxWidth": "250px"}
        )
    ])

# utils.py

def create_user_status_widget(empid, contractor):
    """
    Generates a 'Mini Widget' showing the current login context.
    """
    contractor_display = contractor if contractor else "Internal / All Scope"
    
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                # Employee Section
                dbc.Col([
                    html.Div([
                        html.I(className="fa-solid fa-circle-user fa-xl text-primary me-3"), 
                        html.Div([
                            # REMOVED 'text-muted' -> Now behaves like main text (Black/White)
                            html.Div("Logged in as", className="small text-uppercase fw-bold", style={'fontSize': '0.7rem', 'opacity': '0.7'}),
                            html.Div(f"EMP ID: {empid}", className="fw-bold", style={'fontSize': '1.1rem'})
                        ], className="d-flex flex-column")
                    ], className="d-flex align-items-center")
                ], width="auto", className="border-end pe-4 me-4"),
                
                # Contractor Section
                dbc.Col([
                    html.Div([
                        html.I(className="fa-solid fa-building-shield fa-xl text-primary me-3"), 
                        html.Div([
                            # REMOVED 'text-muted' -> Now behaves like main text (Black/White)
                            html.Div("Contractor Scope", className="small text-uppercase fw-bold", style={'fontSize': '0.7rem', 'opacity': '0.7'}),
                            html.Div(contractor_display, className="fw-bold", style={'fontSize': '1.1rem'})
                        ], className="d-flex flex-column")
                    ], className="d-flex align-items-center")
                ], width="auto")
            ], className="justify-content-center align-items-center g-0")
        ], className="p-2")
    ], className="mb-4 shadow-sm", style={"borderLeft": "5px solid var(--primary-color)"})
