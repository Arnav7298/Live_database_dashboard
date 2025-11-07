# data.py
import pandas as pd
import numpy as np

# practice database
CSV_FILE = 'practice_employee_data.csv'

def get_data():
    """
    Loads data from the 'practice_employee_data.csv' file
    and then populates it with simulated data for testing.
    """
    
    try:
        # 1. Load "safe" data
        df = pd.read_csv(CSV_FILE)
        df_populated = df.copy()
        
        # 2. Clean the data 
        df_populated['gender'] = df_populated['gender'].str.title().fillna('Unknown')
        df_populated['job_title'] = df_populated['job_title'].astype(str).str.title().fillna('Not Available')
        df_populated['department_name'] = df_populated['department_name'].astype(str).str.title().fillna('No Department')

        # 3.START DATA SIMULATIONN
        # (Same logic as test Colab notebook)
        
        print("Loading from CSV... Simulating practice data...")
        
        # Simulate 'joining_date'
        start_date = pd.to_datetime('2020-01-01')
        end_date = pd.to_datetime('2025-10-01')
        total_days = (end_date - start_date).days
        random_days = np.random.randint(0, total_days, size=len(df_populated))
        df_populated['joining_date'] = start_date + pd.to_timedelta(random_days, unit='D')

        # Simulate 'resign_date' and 'departure_reason' for 40% of employees
        num_to_resign = int(len(df_populated) * 0.4)
        departure_reasons = ['Resigned for better opportunity', 'Fired', 'Retired', 'Personal Reasons']
        active_indices = df_populated.index
        indices_to_resign = np.random.choice(active_indices, size=num_to_resign, replace=False)

        for idx in indices_to_resign:
            joining_date = df_populated.loc[idx, 'joining_date']
            days_after_joining = (pd.Timestamp.now() - joining_date).days
            random_days = np.random.randint(365, max(366, days_after_joining))
            resign_date = joining_date + pd.to_timedelta(random_days, unit='D')
            df_populated.loc[idx, 'resign_date'] = resign_date
            df_populated.loc[idx, 'departure_reason'] = np.random.choice(departure_reasons)
            
        # Simulate 'salary'
        random_salaries = np.random.randint(35000, 150000, size=len(df_populated))
        df_populated['salary'] = random_salaries

        # Simulate 'shift_name'
        shifts = ['Shift A', 'Shift B', 'Shift C', 'General Shift', 'No Shift Assigned']
        df_populated['shift_name'] = np.random.choice(shifts, size=len(df_populated), p=[0.2, 0.2, 0.2, 0.3, 0.1])
        
        # Simulate 'required_capacity'
        df_populated['required_capacity'] = np.random.randint(5, 20, size=len(df_populated))
        
        #4. Feature Engineering (for the dashboard)
        df_populated['resign_date'] = pd.to_datetime(df_populated['resign_date'], errors='coerce')
        df_populated['employee_status'] = np.where(df_populated['resign_date'].isnull(), 'Active', 'Departed')
        df_populated['tenure_years'] = (df_populated['resign_date'] - df_populated['joining_date']).dt.days / 365.25

        print("Practice data simulation complete.")
        return df_populated
        
    except FileNotFoundError:
        print(f"Error: The file '{CSV_FILE}' was not found.")
        print("Please export the data from DBeaver and save it in the correct folder.")
        return pd.DataFrame(columns=[
            'employee_id', 'department_name', 'gender', 'job_title', 
            'shift_name', 'required_capacity', 'employee_status', 'tenure_years'
        ])
    except Exception as e:
        print(f"An error occurred: {e}")
        return pd.DataFrame()