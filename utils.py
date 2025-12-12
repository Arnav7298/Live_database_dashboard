# THIS FILE CONTAINS THE DATABASE CONNECTION AND HELPER FUNCTIONS FOR THE DASHBOARD

import pandas as pd
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
from dash import html

# ---------------------------------------------------------
# 1. DATABASE CONNECTION
# ---------------------------------------------------------
db_connection_str = 'postgresql://lumaxuat:lumaxuat@4.247.149.0:9832/lumaxuat'
db_connection = create_engine(db_connection_str)

# ---------------------------------------------------------
# 2. DROPDOWN HELPERS
# ---------------------------------------------------------

def get_plant_options():
    """
    Fetches Plant IDs, Locations, and Codes.
    Returns: [{'label': 'Chakan (P01)', 'value': 7}, ...]
    """
    try:
        query = "SELECT id, location, plant_code FROM plant_plant"
        df = pd.read_sql(query, db_connection)
        
        return [{
            'label': f"{row['location']} ({row['plant_code']})", 
            'value': row['id']
        } for index, row in df.iterrows()]
    except:
        return []

def get_company_options():
    """
    Fetches Companies present in the Attendance table.
    Hides IDs for clients, showing specific names for ID 4 and 8.
    """
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
            
            # Label Mapping Logic
            label = f"Company {cid}" # Default
            if cid == 4: label = "LATL"
            if cid == 8: label = "LIL"
            
            options.append({'label': label, 'value': cid})
            
        return options
    except:
        return []

def get_emp_type_options():
    """
    Static options for Employee Type.
    """
    return [
        {'label': 'Employee', 'value': 'employee'},
        {'label': 'Contractor', 'value': 'contractor'}
    ]

# ---------------------------------------------------------
# 3. FORMATTING HELPERS
# ---------------------------------------------------------

def decimal_to_time_str(val):
    """
    Converts decimal hours (e.g., 1.5) to string format ("1h 30m")
    Used for Graph text labels
    """
    if pd.isna(val) or val == 0:
        return ""
    hours = int(val)
    minutes = int(round((val - hours) * 60))
    return f"{hours}h {minutes}m"


# ---------------------------------------------------------
# 4. COMMON SQL BUILDER (UPDATED)
# ---------------------------------------------------------

def build_base_query(plant_id, company_id, emp_type, contractor_id=None):
    """
    Constructs standard WHERE clauses.
    Now accepts optional 'contractor_id' for restriction.
    """
    conditions = []
    joins = "LEFT JOIN hr_employee e ON a.employee_id = e.id"
    
    if company_id: 
        conditions.append(f"e.company_id = {company_id}")
    
    if plant_id: 
        conditions.append(f"e.plant_id = {plant_id}")
        
    if emp_type: 
        conditions.append(f"LOWER(e.employee_type) = LOWER('{emp_type}')")

    # --- NEW CONTRACTOR RESTRICTION ---
    if contractor_id:
        conditions.append(f"e.contractor_id = {contractor_id}")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    return joins, where_clause
