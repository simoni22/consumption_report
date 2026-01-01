FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY consumption_report.py .
COPY test.py .
COPY dates_calculator.py .
COPY grace_period_subtract.py .
COPY grace_periods.xlsx .
ENTRYPOINT ["python3", "consumption_report.py"]
CMD []