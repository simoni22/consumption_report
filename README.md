# Run:AI Consumption Report Generator

A comprehensive command-line tool and automated Jenkins pipeline system for generating detailed resource consumption reports from a Run:ai cluster. This project overcomes the limitation of the Run:ai API (which only supports single-month queries) by intelligently fetching and merging multiple reports. It supports both Department-level and Project-level reporting with advanced features including grace period deductions, flexible date range options, and automated email delivery.

## Features ✨

### Core Reporting Features
* **Flexible Date Range Options**: 
  * Custom date ranges (e.g., June 20th to August 10th)
  * Monthly reports (`--month 7 2025`)
  * Quarterly reports (`--quarter 4 2025`)
  * Half-year reports (`--half_year 1 2025`)
* **Multiple Report Types**:
  * Department-level aggregation (all departments consolidated)
  * Project-level detailed reports for a specific department (grouped by Department and Project with subtotal row)
* **Grace Period Management**: Automatically deducts grace period consumption from reports using an Excel configuration file
* **Cost Calculation**: Automatically calculates costs for GPU ($0.65/hr), CPU ($0.004/hr), and RAM ($0.001/GB-hr)
* **Concurrent Processing**: Uses ThreadPool with multiple workers to download and process multiple reports simultaneously
* **Department Filtering**: Include or exclude specific departments/projects from reports

### Automation & DevOps Features
* **Jenkins Integration**: Two automated pipelines for scheduled report generation and distribution
  * **Monthly Project Reports**: Sends individual reports to department users
  * **Half-Year Department Reports**: Sends consolidated reports to DevOps team
* **Automated Email Delivery**: Reports are automatically emailed with attachments using Jenkins emailext plugin
* **Smart Error Handling**: DevOps-only error notifications, users only receive successful reports
* **Concurrent Build Protection**: Prevents file corruption with `disableConcurrentBuilds()` option
* **Docker Support**: Containerized deployment with pre-configured dependencies

---

## How It Works: Architecture & Core Logic

### 1. **Unified Date Processing Flow**
The script follows a "normalize-then-process" pattern using the `DatesRangeCalculator` class:

```
User Input (--quarter, --month, --half_year, --start/--end)
    ↓
Normalize to (start_date, end_date) tuple
    ↓
get_api_requests_for_date_range()
    ↓
Generate monthly API requests
    ↓
Concurrent download & processing
    ↓
Merged reports
```

All date input types (quarter, month, half-year, custom range) are converted to a standardized `(start_date, end_date)` pair, then processed through a single unified code path.

### 2. **Overcoming API Limitations**
The Run:ai API only supports single-month queries. The script solves this by:

* **Date Range Segmentation**: When you provide a date range (e.g., June 20 to August 10), the `DatesRangeCalculator.adding_monthly_reports()` function segments it into:
  * Partial first month (June 20-30)
  * Full intermediate months (all of July)
  * Partial final month (August 1-10)

* **Concurrent Fetching**: Uses ThreadPoolExecutor with multiple workers to download reports in parallel, with automatic retry logic and status polling

* **Random Report Names**: Generates unique random names for each API request to prevent naming conflicts when multiple users create reports simultaneously

### 3. **Data Processing Pipeline**
Each downloaded report goes through:

1. **Filtering**: Apply include/exclude department filters (if specified)
2. **Transformation** (`change_df`): 
   - Remove unnecessary columns
   - Convert memory bytes to GB
   - Calculate costs: GPU ($0.65/hr), CPU ($0.004/hr), RAM ($0.001/GB-hr)
3. **Aggregation** (`merge_reports`):
   - Department reports: Group by Department
   - Project reports: Group by Department + Project, with automatic subtotal row

### 4. **Grace Period Deduction**

**Department Reports:** After generating the main report, the script processes grace periods:

1. Reads grace period definitions from `grace_periods.xlsx`
2. Checks for date range overlaps between report and grace periods
3. For each overlap:
   - Generates a separate grace period report using the same unified flow
   - Downloads it with department/project filters
   - Subtracts resource usage from the main report
4. Saves the adjusted report as `consumption_report_adjusted.xlsx`

**Project Reports:** Optimized grace period handling:

1. Checks if the requested date range overlaps with any grace period for the specified department
2. If overlap exists, automatically adjusts the API request to fetch only post-grace-period data
3. This optimization reduces API calls and eliminates the need for post-processing subtraction
4. Only the main report file is generated (no adjusted file needed)

---

## 📁 Project Structure

```
consumption_report/
├── consumption_report.py          # Main script for report generation
├── dates_calculator.py            # Date range calculation and API request generation
├── grace_period_subtract.py       # Grace period handling and deduction logic
├── test.py                        # API request handling and Run:ai integration (NOT INCLUDED - see below)
├── grace_periods.xlsx             # Grace period configuration (Department, mail, start, end)
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker container configuration
├── Jenkinsfile.monthly            # Jenkins pipeline for monthly project reports
├── Jenkinsfile.halfyear           # Jenkins pipeline for half-year department reports
├── JENKINS_SETUP.md              # Complete Jenkins setup and configuration guide
├── README.md                      # This file
└── env/                          # Python virtual environment (created during setup)
```

---

## ⚠️ Important Note: API Integration File Not Included

The `test.py` file is **not included in this repository** for security reasons.

**What test.py does:**
- Handles all API communication with the Run.ai cluster
- Contains the `APIRequest` class that manages:
  - Authentication (token generation using app credentials)
  - Report creation via API endpoints
  - Report status polling (waits for reports to be ready)
  - Report download (fetches CSV data and converts to pandas DataFrame)
  - Report deletion (cleanup after download)
  - Random report name generation to prevent conflicts

**Why it's not included:**
This file contains sensitive information that cannot be shared publicly:
- Organization-specific API credentials (App ID and App Secret)
- Organization-specific Run.ai cluster URLs
- Internal authentication mechanisms

**To use this project:**
You would need to implement your own API client that connects to your Run.ai instance. The `APIRequest` class should provide methods that the main scripts expect:
- `__init__(dates)` - Constructor that takes date range
- `download_report(report_type, filtered_user)` - Returns a pandas DataFrame with consumption data

The project architecture is designed to work with any Run.ai cluster by implementing this interface with your own credentials and endpoints.

---

## 📂 Output Files and Paths

The script generates output files in the following locations:

### Local Execution
Files are saved to `~/consumption_report/` (user's home directory):

**Department Reports:**
- `consumption_report.xlsx` - Main department report
- `consumption_report_adjusted.xlsx` - After grace period deductions (if applicable)

**Project Reports:**
- `consumption_report.xlsx` - Main project report for specified department
  - Includes SUBTOTAL row with aggregated values
  - Grace periods are pre-applied (no adjusted file needed)

### Jenkins Execution
For automated Jenkins pipelines:

**Working Directory:** Jenkins checks out code to `${WORKSPACE}` (e.g., `/var/lib/jenkins/workspace/Monthly-Consumption-Reports/`)

**Output Location:** `~/consumption_report/` (Jenkins user's home directory, typically `/var/lib/jenkins/consumption_report/`)

**Workspace Copies:** Temporary copies are created in `${WORKSPACE}/` for email attachments with naming pattern:
- Monthly: `consumption_report_<department>_<month>_<year>.xlsx`
- Half-year: `consumption_report_departments_H<1|2>_<year>.xlsx`

**Cleanup:** Workspace copies are automatically deleted after email is sent

---

## 📧 Automated Email Delivery (Jenkins)

The project includes two Jenkins pipelines that automatically generate and email reports:

### 1. Monthly Project Reports (`Jenkinsfile.monthly`)
- **Schedule:** 2nd of every month at 9:00 AM
- **Report Period:** Previous month (e.g., runs Sept 2 → reports August)
- **Recipients:** Individual users per department (from `grace_periods.xlsx`)
- **Email Contains:** 
  - Excel report attachment for their specific department
  - Report period in subject line
  - Professional email body from "HPC DevOps team"
- **DevOps Monitoring:** One summary email with success/failure counts and details

### 2. Half-Year Department Reports (`Jenkinsfile.halfyear`)
- **Schedule:** January 1st and July 1st at 9:00 AM
- **Report Period:** Previous half-year (Jan 1 → H2 of previous year, Jul 1 → H1 of current year)
- **Recipients:** DevOps team only
- **Email Contains:**
  - Consolidated department report for all departments
  - Success: Report attachment with summary
  - Failure: Error notification with console link (no report sent to users)

**Email Features:**
- Automatic attachment of Excel reports
- No error emails sent to end users (DevOps only)
- Console output links for debugging
- Build number and timestamp tracking

See [JENKINS_SETUP.md](JENKINS_SETUP.md) for complete configuration instructions.

---

## Prerequisites

* Python 3.8+
* `pip` (Python package installer)

---

## ⚙️ Setup and Installation

1.  **Clone the Repository**
    ```bash
    git clone <your-repo-link>
    cd <your-repo-directory>
    ```

2.  **Create and Activate a Virtual Environment**
    A virtual environment keeps your project dependencies isolated.

    * **Create:**
        ```bash
        python -m venv env
        ```
    * **Activate (macOS/Linux):**
        ```bash
        source env/bin/activate
        ```
    * **Activate (Windows):**
        ```bash
        .\env\Scripts\activate
        ```

3.  **Install Dependencies**
    Install all the required Python libraries from the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

---


## 🚀 Usage and Examples

### Basic Commands

**Generate a Department Report for a Custom Date Range:**
```bash
python3 consumption_report.py --start 2025-10-05 --end 2025-11-15 --Department
```

**Generate a Monthly Report:**
```bash
python3 consumption_report.py --month 7 2025 --Department
```

**Generate a Quarterly Report:**
```bash
python3 consumption_report.py --quarter 3 2025 --Department
```

**Generate a Half-Year Report:**
```bash
python3 consumption_report.py --half_year 1 2025 --Department
```

### Project-Level Reports

**Generate Project Report for a Specific Department:**
```bash
python3 consumption_report.py --quarter 3 2025 --Project hpc
```

**Project Report with Date Range:**
```bash
python3 consumption_report.py --start 2025-07-01 --end 2025-07-25 --Project engineering
```

**Project Report for Another Department:**
```bash
python3 consumption_report.py --month 11 2025 --Project research
```

> **Note:** Project reports show all projects under the specified department name and include a SUBTOTAL row at the bottom that sums all numeric columns.

### Department Filtering

**Include Only Specific Departments:**
```bash
python3 consumption_report.py --quarter 3 2025 --Department --include sales research devops
```

**Exclude Specific Departments:**
```bash
python3 consumption_report.py --start 2025-01-01 --end 2025-01-31 --Department --exclude admin testing
```

### Docker Usage

The Dockerfile creates a containerized environment for running consumption reports:

**Build the Docker Image:**
```bash
docker build -t consumption-report .
```

**Run Department Report with Docker:**
```bash
docker run -v $(pwd)/grace_periods.xlsx:/app/grace_periods.xlsx \
           -v $(pwd)/output:/root/consumption_report \
           consumption-report --quarter 4 2025 --Department
```

**Run Project Report with Docker:**
```bash
docker run -v $(pwd)/grace_periods.xlsx:/app/grace_periods.xlsx \
           -v $(pwd)/output:/root/consumption_report \
           consumption-report --month 11 2025 --Project hpc
```

**What's Included in the Container:**
- Python 3.12-slim base image
- All required Python dependencies from `requirements.txt`
- All Python scripts: `consumption_report.py`, `test.py`, `dates_calculator.py`, `grace_period_subtract.py`
- `grace_periods.xlsx` configuration file
- Output is written to `/root/consumption_report/` inside container (mount a volume to persist)

**Volume Mounts Explained:**
- `-v $(pwd)/grace_periods.xlsx:/app/grace_periods.xlsx` - Mounts your local grace periods config
- `-v $(pwd)/output:/root/consumption_report` - Mounts output directory to save reports locally

**Help - See All Available Options:**
```bash
python3 consumption_report.py -h
```

---

## 📋 Command-Line Arguments

### Date Range Options (choose one):
- `--start YYYY-MM-DD --end YYYY-MM-DD` - Custom date range
- `--month M YEAR` - Single month (e.g., `--month 7 2025`)
- `--quarter Q YEAR` - Quarter 1-4 (e.g., `--quarter 4 2025`)
- `--half_year H YEAR` - Half year 1 or 2 (e.g., `--half_year 1 2025`)

### Report Type (required):
- `--Department` - Aggregate by department only
- `--Project DEPARTMENT_NAME` - Generate detailed report for specified department, showing all projects grouped by Department and Project, with a subtotal row

### Filters (optional):
- `--include DEPT1 DEPT2 ...` - Include only specified departments
- `--exclude DEPT1 DEPT2 ...` - Exclude specified departments

---

## 📁 Output Files

The script generates Excel files with different naming conventions based on report type and execution context:

### Local/Manual Execution Output

All files are saved to `~/consumption_report/` (your home directory):

**Department Reports:**
1. **`consumption_report.xlsx`** - Initial report with all departments aggregated
2. **`consumption_report_adjusted.xlsx`** - Final report after grace period deductions (if applicable)

**Project Reports:**
1. **`consumption_report.xlsx`** - Report with all projects under the specified department
   - Includes automatic SUBTOTAL row summing all numeric columns
   - Grace periods are pre-applied by adjusting date ranges (no adjusted file needed)

### Jenkins Automated Execution Output

**Working Directory:** `${WORKSPACE}` (e.g., `/var/lib/jenkins/workspace/Monthly-Consumption-Reports/`)

**Permanent Output:** Same as local execution (`~/consumption_report/`)

**Temporary Files (for email attachments):**
- Created in `${WORKSPACE}/` with unique names
- Monthly: `consumption_report_<department>_<month>_<year>.xlsx`
- Half-year: `consumption_report_departments_H<1|2>_<year>.xlsx`
- **Automatically deleted** after email is sent to prevent disk clutter

### File Lifecycle in Jenkins

```
Generate Report → Save to ~/consumption_report/consumption_report_*.xlsx
                                    ↓
                  Copy to workspace with unique name
                                    ↓
                  Attach to email and send
                                    ↓
                  Delete workspace copy
                                    ↓
                  Next department overwrites ~/consumption_report/consumption_report_*.xlsx
```

This design ensures:
- No concurrent build conflicts (protected by `disableConcurrentBuilds()`)
- Minimal disk usage (only one permanent file + temporary workspace copies)
- Clean workspace after each run

---

## 🔧 Grace Periods Configuration

Create a `grace_periods.xlsx` file in the project root with the following structure:
- `Department` - Name
- `mail` - User mail address
- `start` - Grace period start date (DD.MM.YYYY format)
- `end` - Grace period end date (DD.MM.YYYY format)