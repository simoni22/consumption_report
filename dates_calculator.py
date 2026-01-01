from dateutil import tz
import calendar
import datetime
import pandas as pd
import argparse
from test import APIRequest


class DatesRangeCalculator:
    IL_TZ = tz.gettz("Israel")

        
    def calculate_month(start, finish):
        # returns range of days to handle each month report
        if start[0] != finish[0] or start[1] != finish[1]:
            # first and middle months
            start_date = datetime.datetime(start[0], start[1], start[2], 0, 0, 0, tzinfo=DatesRangeCalculator.IL_TZ)
            end_date = datetime.datetime(start[0], start[1], calendar.monthrange(start[0], start[1])[1], 23, 59, 59, tzinfo=DatesRangeCalculator.IL_TZ)
            return {"start": start_date.isoformat(), "end": end_date.isoformat()}
        else:
            # last month
            return {"start": datetime.datetime(start[0], start[1], start[2], 0, 0, 0, tzinfo=DatesRangeCalculator.IL_TZ).isoformat(), "end":datetime.datetime(finish[0], finish[1], finish[2], 23, 59, 59, tzinfo=DatesRangeCalculator.IL_TZ).isoformat()}
        
        
    def update_date(start):
        if start[1] == 12:
            start[0] += 1
            start[1] = 1
            start[2] = 1
        else:
            start[1] += 1
            start[2] = 1
    
    
    def adding_monthly_reports(start, finish):
        reports = []
    
        while start[0] != finish[0] or start[1] != finish[1]:
            reports.append(APIRequest(dates=DatesRangeCalculator.calculate_month(start, finish)))
            DatesRangeCalculator.update_date(start)

        reports.append(APIRequest(dates=DatesRangeCalculator.calculate_month(start, finish)))
        return reports
    
    
    def get_quarter_range(quarter_args):
        quarter = int(quarter_args[0])
        year = int(quarter_args[1])
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime.date(year, start_month, 1)
        end_month = start_month + 2
        _, last_day = calendar.monthrange(year, end_month)
        end_date = datetime.date(year, end_month, last_day)
        return start_date, end_date
    
    
    def get_month_range(month_args):
        month = int(month_args[0])
        year = int(month_args[1])
        start_date = datetime.date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime.date(year, month, last_day)
        return start_date, end_date
    
    
    def get_half_year_range(half_year_args):
        half = int(half_year_args[0])
        year = int(half_year_args[1])
        start_month = 1 if half == 1 else 7
        start_date = datetime.date(year, start_month, 1)
        end_month = start_month + 5
        _, last_day = calendar.monthrange(year, end_month)
        end_date = datetime.date(year, end_month, last_day)
        return start_date, end_date
    
    
    def get_date_range(args):
        # Extract start and end dates range from args
        start_parts = [int(part) for part in args.start.split('-')]
        end_parts = [int(part) for part in args.end.split('-')]
        start_date = datetime.date(start_parts[0], start_parts[1], start_parts[2])
        end_date = datetime.date(end_parts[0], end_parts[1], end_parts[2])
    
        return start_date, end_date
    
    
    def get_api_requests_for_date_range(start_date, end_date):
        # Convert date range to list of API Request objects
        if start_date > end_date:
            raise ValueError(f"Start date {start_date} cannot be after end date {end_date}, check whether you are asking for the correct date range.")
        start_list = [start_date.year, start_date.month, start_date.day]
        end_list = [end_date.year, end_date.month, end_date.day]
        return DatesRangeCalculator.adding_monthly_reports(start_list, end_list)