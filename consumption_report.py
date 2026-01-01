import concurrent.futures
import argparse
from re import match
import pandas as pd
import os
from test import APIRequest
import grace_period_subtract
from dates_calculator import DatesRangeCalculator


OUTPUT_PATH = os.path.join(
    os.path.expanduser('~'), 'consumption_report', 'consumption_report.xlsx')

MAX_CONCURRENT_THREADS = 6
GPU , CPU , RAM = 0.65, 0.004, 0.001  # Cost per unit


def merge_reports(df, report_type):
    if report_type == "Department":
        return pd.concat(df).groupby(['Department']).sum().reset_index() 
    else:
        return pd.concat(df).groupby(['Department', 'Project']).sum().reset_index()


def change_df(gpu,cpu,ram,df):
    df.drop(['Cluster', 'CPU Memory bytes usage hours', 'CPU cores usage hours', 'GPU Idle hours'], axis='columns', inplace=True)
    df.loc[:,'CPU Memory bytes allocation hours']*= 10**(-9)
    df.rename(columns={"CPU Memory bytes allocation hours":"CPU Memory GB allocation hours"},inplace=True)
    df["GPU cost"]=df["GPU allocation hours"]*gpu
    df["CPU cost"]=df["CPU cores allocation hours"]*cpu
    df["Memory cost"]=df["CPU Memory GB allocation hours"]*ram
    df["Total Cost"]=df["GPU cost"]+df["CPU cost"]+df["Memory cost"]
    return df


def drop_rows(report,delete, report_type):
    # do not include this departments in the report
     return report[~report[report_type].isin(delete)].copy()


def leave_row(report,leave, report_type):
    # include only this departments in the report
    return report[report[report_type].isin(leave)].copy()


def setup_arg_parser():
    """Sets up and returns the validated argument parser."""
    parser = argparse.ArgumentParser(description="Generate a consumption report for a given date range.")
    
    # Date input
    date_input_group = parser.add_mutually_exclusive_group(required=True)
    date_input_group.add_argument("--quarter", nargs=2, metavar=('Q', 'YEAR'),
                                  help="Generate a report for a specific quarter and year (e.g., 4 2025).")
    date_input_group.add_argument("--start", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format.")
    date_input_group.add_argument("--month", nargs=2, metavar=('M', 'YEAR'),
                                  help="Generate a report for a specific month (e.g., 11 2025).")
    date_input_group.add_argument("--half_year", nargs=2, metavar=('H', 'YEAR'),
                                  help="Generate a report for a specific half year (e.g., 1 2025).")
    
    # Filters
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument("--include", nargs='+', help="Departments to include in the report.")
    filter_group.add_argument("--exclude", nargs='+', help="Departments to exclude from the report.")
    
    # Report type
    report_type = parser.add_mutually_exclusive_group(required=True)
    report_type.add_argument("--Department", action="store_true", help="Group report by Department.")
    report_type.add_argument("--Project", nargs=1, metavar=('DNAME'), help="Group report by Department, show projects.")
    
    return validate_args(parser)
    
    
def validate_args(parser):
    args = parser.parse_args()
    if args.start and not args.end:
        parser.error("The --start argument requires the --end argument.")
    if args.end and not args.start:
        parser.error("The --end argument requires the --start argument.")
    return args


def get_report_type_from_args(args):
    return "Department" if args.Department else "Project"


def type_of_custom_date_range(args):
    # match case of date range input
    if args.quarter:
        return DatesRangeCalculator.get_quarter_range(args.quarter)
    elif args.month:
        return DatesRangeCalculator.get_month_range(args.month)
    elif args.half_year:
        return DatesRangeCalculator.get_half_year_range(args.half_year)
    else:
        return DatesRangeCalculator.get_date_range(args)
        

def get_report_requests_from_args(args):
    # Takes parsed arguments and returns a list of APIRequest objects
    try:
        # Normalize ALL inputs to (start_date, end_date)
        if args.quarter:
            quarter = int(args.quarter[0])
            year = int(args.quarter[1])
            if not 1 <= quarter <= 4:
                raise ValueError("Quarter must be between 1 and 4.")
            print(f"Generating report for Q{quarter} {year}...")
            start_date, end_date = DatesRangeCalculator.get_quarter_range(args.quarter)
            
        elif args.month:
            month = int(args.month[0])
            year = int(args.month[1])
            if not 1 <= month <= 12:
                raise ValueError("Month must be between 1 and 12.")
            print(f"Generating report for {month}/{year}...")
            start_date, end_date = DatesRangeCalculator.get_month_range(args.month)
            
        elif args.half_year:
            half = int(args.half_year[0])
            year = int(args.half_year[1])
            if half not in [1, 2]:
                raise ValueError("Half year must be 1 or 2.")
            print(f"Generating report for semi year: {half} {year}...")
            start_date, end_date = DatesRangeCalculator.get_half_year_range(args.half_year)

        else:
            print(f"Generating report from {args.start} to {args.end}...")
            start_date, end_date = DatesRangeCalculator.get_date_range(args)
            
        # Single unified path for all date types
        return DatesRangeCalculator.get_api_requests_for_date_range(start_date, end_date)
    
    except (ValueError, IndexError) as e:
        print(f"Error: Invalid date format. {e}. Please provide dates in the correct format.")
        return []
    

def adding_subtotal_row(merged_df, args):
    subtotal_row = {
    'Department': args.Project[0],
    'Project': 'SUBTOTAL'
    }
    # Sum all numeric columns
    for col in merged_df.select_dtypes(include=['number']).columns:
        subtotal_row[col] = merged_df[col].sum()
    # Append subtotal row
    return pd.concat([merged_df, pd.DataFrame([subtotal_row])], ignore_index=True)


def process_and_save_reports(reports, args, output_path=None):
    # Downloads reports concurrently, then filters, processes, and saves them
    if not reports:
        return

    df_list = []
    total_reports = len(reports)
    processed_reports = 0
    
    report_type = get_report_type_from_args(args)
    if args.Project:
        filtered_user = args.Project[0]
    else:
        filtered_user = None
    
    # Use custom output path if provided, otherwise use default
    if output_path is None:
        output_path = OUTPUT_PATH
    else:
        # If it's just a filename, build the full path
        if not os.path.isabs(output_path):
            output_path = os.path.join(os.path.expanduser('~'), 'consumption_report', output_path)
    
    with concurrent.futures.ThreadPoolExecutor(MAX_CONCURRENT_THREADS) as executor:
        # Submit all download tasks
        futures = [executor.submit(lambda r=report: r.download_report(report_type, filtered_user)) 
           for report in reports]
        
        # Wait for each download to complete and process it
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                df = future.result()  # This will wait for the download to complete
                if df is not None:
                    print(f"Successfully downloaded report {i+1}")
                    
                    # Apply filters if specified
                    if args.include:
                        df = leave_row(df, args.include, report_type)
                    elif args.exclude:
                        df = drop_rows(df, args.exclude, report_type)
                    
                    # Process individual report if not empty
                    if not df.empty:
                        df = change_df(df=df, gpu=GPU, cpu=CPU, ram=RAM)
                        df_list.append(df)
                        processed_reports += 1
                    else:
                        print(f"Report {i+1} was empty or had no data after filtering")
                else:
                    print(f"Report {i+1} download failed or was empty")
            except Exception as e:
                print(f"Error processing report {i+1}: {e}")
    
    # Create final merged report and save it
    if processed_reports > 0:
        if processed_reports == total_reports:
            print(f"Successfully processed all {processed_reports} reports")
        else:
            print(f"Only processed {processed_reports} out of {total_reports} reports")
            
        merged_df = merge_reports(df_list, report_type)
        if report_type == "Project" and args.Project is not None:
            merged_df = adding_subtotal_row(merged_df, args)
        merged_df.to_excel(output_path, index=False)
        print(f"Report '{os.path.basename(output_path)}' generated successfully!")
        
    else:
        print("No data was processed. No report was generated.")


def department_report(args):
    reports_to_fetch = get_report_requests_from_args(args)
    process_and_save_reports(reports_to_fetch, args)
    
    # Get date range for grace period processing
    start_date, end_date = type_of_custom_date_range(args)
    
    report_type = get_report_type_from_args(args)
    # Process grace period subtractions for all departments
    grace_period_subtract.process_all_departments(
        OUTPUT_PATH,
        start_date,
        end_date,
        report_type
    )
    os.remove(OUTPUT_PATH)


def project_report(args):
    start_date, end_date = type_of_custom_date_range(args) # Command line date range
    if grace_period_subtract.is_subtraction_needed(start_date, end_date, "Project", args.Project[0]):
        [_, end] = grace_period_subtract.overlap_dates(
            start_date, end_date, "Project", args.Project[0]) # Overlapping grace period dates
        start_date = end + pd.Timedelta(days=1)  # Adjust start date to exclude grace period
        if start_date > end_date:
            # Create a minimal Excel report with explanation
            explanation_df = pd.DataFrame([{
                'Department': args.Project[0],
                'Project': 'N/A',
                'Message': f'No consumption data - entire period ({type_of_custom_date_range(args)[0]} to {type_of_custom_date_range(args)[1]}) falls within grace period'
            }])
            output_path = os.path.join(os.path.expanduser('~'), 'consumption_report', 'consumption_report.xlsx')
            explanation_df.to_excel(output_path, index=False)
            print(f"Generated empty report with explanation for {args.Project[0]}")
            return
            
    process_and_save_reports(
        DatesRangeCalculator.get_api_requests_for_date_range(start_date, end_date), args)
    

if __name__== "__main__":
    args = setup_arg_parser()
    if args.Department:
        department_report(args)
    else:
        project_report(args)