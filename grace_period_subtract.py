import pandas as pd
import consumption_report
import os
from dates_calculator import DatesRangeCalculator


ADJUSTED_OUTPUT_PATH = os.path.join(
    os.path.expanduser('~'), 'consumption_report', 'consumption_report_adjusted.xlsx')

# Use path relative to script location to work in both local and Jenkins environments
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GRACE_PERIODS_PATH = os.path.join(SCRIPT_DIR, 'grace_periods.xlsx')

df = pd.read_excel(GRACE_PERIODS_PATH)
# Convert date columns to proper format assuming day/month/year
if 'start' in df.columns:
    df['start'] = pd.to_datetime(df['start'], dayfirst=True)
if 'end' in df.columns:
    df['end'] = pd.to_datetime(df['end'], dayfirst=True)


def get_user_df(report_type, user):
    return df[df["Department"] == user]


def excel_date_parser(report_type, user):
    # Returns a list of start and end grace dates for this department/project as datetime.date objects
    user_data = get_user_df(report_type, user)
    if user_data.empty:
        return None, None
    
    # Get date values (already parsed as datetime objects)
    start_date = user_data['start'].iloc[0].date()
    end_date = user_data['end'].iloc[0].date()
    
    return [start_date, end_date]


def is_subtraction_needed(start, end, report_type, user):
    # Checks if a report date range overlaps with grace period, filtered by department/project
    # start and end should be datetime.date objects
    parsed_dates = excel_date_parser(report_type, user)
    grace_start = parsed_dates[0]
    grace_end = parsed_dates[1]
    
    # Check if user has grace period dates
    if grace_start is None or grace_end is None:
        return False
    
    # Check if there's overlap
    if start <= grace_end and end >= grace_start:
        return True
    return False


def overlap_dates(start, end, report_type, user):
    # Returns [start_date, end_date] as datetime.date objects for the overlapping period
    parsed_dates = excel_date_parser(report_type, user)
    grace_start = parsed_dates[0]
    grace_end = parsed_dates[1]
    
    # Check if user has grace period dates
    if grace_start is None or grace_end is None:
        return None
    
    if start >= grace_start and end <= grace_end:
        return [start, end]
    
    # Find the overlapping period
    overlap_start = max(start, grace_start)
    overlap_end = min(end, grace_end)
    
    return [overlap_start, overlap_end]


def generate_grace_reports(start, end, report_type, user):
    # Generates API requests for grace period reports base on overlapping dates
    overlap_period = overlap_dates(start, end, report_type, user)
    overlap_start = overlap_period[0]
    overlap_end = overlap_period[1]
    
    print(f"{report_type} {user} Grace period overlap dates: {overlap_start} to {overlap_end}") # Debug
    # Generate API requests for the grace period
    grace_reports = DatesRangeCalculator.get_api_requests_for_date_range(overlap_start, overlap_end)
    return grace_reports
    
    
def download_grace_reports(grace_reports, report_type, user):
    # Create a mock args object with include filter for the department
    class Args:
        def __init__(self, name):
            if report_type == 'Department':
                self.include = [name]
                self.exclude = None
                self.Department = True
                self.Project = None
            elif report_type == 'Project':
                self.include = [name]
                self.exclude = None
                self.Department = None
                self.Project = [user]
    
    args = Args(user)
    file_name = f'grace_period_{user}.xlsx'
    consumption_report.process_and_save_reports(grace_reports, args, file_name)
    return file_name


def subtract_grace_period(main_df, grace_report_path, report_type, user):
    # Subtracts grace period report from main report for a specific department/project
    grace_df = pd.read_excel(grace_report_path)
    
    # Find the user row in main report
    user_mask = main_df[report_type] == user
    
    if not user_mask.any():
        print(f"{report_type} {user} not found in main report")
        return main_df
    
    if grace_df.empty:
        print(f"Grace period report for {user} is empty")
        return main_df
    
    # Get numeric columns to subtract
    numeric_cols = grace_df.select_dtypes(include=['number']).columns
    
    # Subtract grace period values from main report for this department/project
    if report_type == "Department":
        for col in numeric_cols:
            if col in main_df.columns:
                grace_value = grace_df[col].iloc[0]
                main_df.loc[user_mask, col] = main_df.loc[user_mask, col] - grace_value
    else:  
    # Project case. Find the matching project row in grace report
        grace_user_mask = grace_df[report_type] == user
        if not grace_user_mask.any():
            print(f"Project {user} not found in grace report")
            return main_df
    
        for col in numeric_cols:
            if col in main_df.columns:
                grace_value = grace_df.loc[grace_user_mask, col].iloc[0]
                main_df.loc[user_mask, col] = main_df.loc[user_mask, col] - grace_value
    
    return main_df


def process_all_departments(main_report_path, start, end, report_type):
    # Process all departments that need grace period subtraction
    main_df = pd.read_excel(main_report_path)
    grace_names = df["Department"].unique()
    
    for user in grace_names:
        if is_subtraction_needed(start, end, report_type, user):
            print(f"{report_type}: {user}, Start: {start}, End: {end}") # Debug

            # Get start and end grace dates for this department/project
            parsed_dates = excel_date_parser(report_type, user)
            grace_start = parsed_dates[0]
            grace_end = parsed_dates[1]
            print(f"Grace period: {grace_start} to {grace_end}") # Debug
            
            print(f"Processing grace period for {report_type}: {user}")
            
            # Generate and download grace period reports
            grace_reports = generate_grace_reports(start, end, report_type, user)
            grace_file = download_grace_reports(grace_reports, report_type, user)
            
            # Build full path to grace file
            grace_file_path = os.path.join(os.path.expanduser('~'), 'consumption_report', grace_file)
            
            # Subtract grace period from main report
            main_df = subtract_grace_period(main_df, grace_file_path, report_type, user)
            
            # Clean up grace period file
            try:
                os.remove(grace_file_path)
                print(f"Removed temporary grace period file: {grace_file}")
            except Exception as e:
                print(f"Error removing temporary grace period file: {e}")
    
    # Save the adjusted report
    main_df.to_excel(ADJUSTED_OUTPUT_PATH, index=False)
    print(f"Adjusted report saved to: {ADJUSTED_OUTPUT_PATH}")
    return main_df