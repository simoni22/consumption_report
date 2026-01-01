# Jenkins Automated Consumption Reports Setup Guide

This guide explains how to set up automated consumption reports using Jenkins.

## Overview

This project includes **two separate Jenkins pipelines**:

### 1. Monthly Project Reports (`Jenkinsfile.monthly`)
- **Runs automatically** on the 2nd of every month at 9:00 AM
- **Generates** individual project reports for each department listed in `grace_periods.xlsx`
- **Emails** each report to the corresponding user
- **Reports previous month's data** (e.g., runs on Sept 2 → reports August)
- **Prevents** concurrent builds to avoid file corruption
- **Sends monitoring summary** to DevOps team after completion

### 2. Half-Year Department Reports (`Jenkinsfile.halfyear`)
- **Runs automatically** on January 1st and July 1st at 9:00 AM
- **Generates** one consolidated department report for all departments
- **Emails** report to DevOps team only
- **Reports previous half-year** (Jan 1 → H2 of previous year, Jul 1 → H1 of current year)
- **Prevents** concurrent builds
- **Single email** with report on success, failure notification on error

## Prerequisites

1. Jenkins server with the following plugins:
   - Email Extension Plugin (`emailext`)
   - Pipeline Plugin
   - Git Plugin

2. Jenkins user account on the system

3. Git repository containing this project

## Jenkins Configuration

### Setup for Monthly Project Reports

#### 1. Schedule Configuration

The schedule is **already configured in the Jenkinsfile** using the `triggers` directive:

```groovy
triggers {
    cron('0 9 2 * *')  // Runs at 9:00 AM on the 2nd of every month
}
```

**You don't need to configure this in Jenkins UI** - it's automatic!

However, if you want to change the schedule, you can either:
- **Option A:** Modify the cron expression in the Jenkinsfile
- **Option B:** Configure it in Jenkins UI (Pipeline settings → Build Triggers → Build periodically)

### Cron Expression Format
```
minute hour day month dayOfWeek
0      8    1   *     *
```

Common schedules:
- `0 9 2 * *` - 9:00 AM on the 2nd of every month
- `0 9 15 * *` - 9:00 AM on the 15th of every month
- `0 8 * * 1` - 8:00 AM every Monday
- `0 8 1 1,4,7,10 *` - 8:00 AM on 1st of Jan, Apr, Jul, Oct (quarterly)

#### 2. Create Jenkins Pipeline Job for Monthly Reports

1. **Open Jenkins** → Click "New Item"

2. **Enter job name**: `Monthly-Consumption-Reports`

3. **Select**: "Pipeline" → Click "OK"

4. **Configure the Pipeline**:
   - **Description**: Monthly project consumption reports for individual departments
   - **Build Triggers**: Leave empty (cron is in Jenkinsfile)
   - **Pipeline Definition**: Select "Pipeline script from SCM"
   - **SCM**: Git
   - **Repository URL**: Your Git repository URL
   - **Credentials**: Add if needed
   - **Branch**: `*/range_of_dates` (or your branch name)
   - **Script Path**: `Jenkinsfile.monthly`

5. **Save**

---

### Setup for Half-Year Department Reports

#### 1. Schedule Configuration

The half-year schedule is configured in `Jenkinsfile.halfyear`:

```groovy
triggers {
    cron('0 9 1 1,7 *')  // Runs at 9:00 AM on Jan 1 and Jul 1
}
```

This runs twice per year:
- **January 1st at 9:00 AM** - Reports H2 (July-December) of the previous year
- **July 1st at 9:00 AM** - Reports H1 (January-June) of the current year

#### 2. Create Jenkins Pipeline Job for Half-Year Reports

1. **Open Jenkins** → Click "New Item"

2. **Enter job name**: `HalfYear-Department-Reports`

3. **Select**: "Pipeline" → Click "OK"

4. **Configure the Pipeline**:
   - **Description**: Half-year department consumption reports for DevOps team
   - **Build Triggers**: Leave empty (cron is in Jenkinsfile)
   - **Pipeline Definition**: Select "Pipeline script from SCM"
   - **SCM**: Git
   - **Repository URL**: Your Git repository URL (same as monthly)
   - **Credentials**: Same as monthly
   - **Branch**: `*/range_of_dates` (or your branch name)
   - **Script Path**: `Jenkinsfile.halfyear`

5. **Save**

---

### Email Configuration (Both Pipelines)

Configure Jenkins email settings:

1. **Jenkins** → **Manage Jenkins** → **Configure System**

2. **Extended E-mail Notification** section:
   - **SMTP server**: Your SMTP server (e.g., `smtp.gmail.com`)
   - **SMTP Port**: 587 (for TLS) or 465 (for SSL)
   - **Credentials**: Add email credentials
   - **Use SSL/TLS**: Check if required

3. **Test** by clicking "Test configuration by sending test e-mail"

## Jenkins User Setup on the System

The Jenkins user needs to be set up on the Linux system:

### Create Jenkins User (if not exists)
```bash
sudo useradd -m -s /bin/bash jenkins
```

### Set up SSH keys for Git (if using SSH)
```bash
sudo su - jenkins
ssh-keygen -t rsa -b 4096 -C "jenkins@yourdomain.com"
# Add the public key to your Git repository
cat ~/.ssh/id_rsa.pub
```

### Grant Permissions
```bash
# Ensure Jenkins user can access necessary directories
sudo usermod -aG <your-group> jenkins
```

## How the Pipelines Work

### Monthly Project Reports Pipeline

#### Automatic Setup (First Run)

On the first run, the pipeline automatically:

1. **Creates Python virtual environment** at `${WORKSPACE}/env`
2. **Installs requirements** from `requirements.txt`
3. **Creates output directory** at `~/consumption_report/`

#### Subsequent Runs

On subsequent runs:

1. **Updates Python packages** (if requirements.txt changed)
2. **Processes each department** sequentially from `grace_periods.xlsx`

#### Department Processing

For each department in `grace_periods.xlsx`:

1. Reads department name and email from columns: `Department`, `mail`
   - **Note**: `start` and `end` columns are NOT used by Jenkins
   - Those columns are only used by the Python consumption report scripts for grace period calculations

2. Generates **previous month** project report using:
   ```bash
   python3 consumption_report.py --month <previous_month> <report_year> --Project <department>
   ```
   - The month and year are automatically calculated using `date -d 'last month'`
   - Example: Running on September 1st, 2025 → generates report for month 8 (August) 2025
   - Example: Running on January 1st, 2025 → generates report for month 12 (December) 2024

3. Emails the report to the specified user email address

4. Waits 2 seconds before processing next department

5. **After all departments**: Sends one summary email to DevOps with:
   - Total successful reports
   - Total failed reports
   - List of failed departments (if any)
   - Build duration and links

---

### Half-Year Department Reports Pipeline

#### How It Works

1. **Determines the reporting period**:
   - If running on **January 1st** → Reports H2 (July-December) of **previous year**
   - If running on **July 1st** → Reports H1 (January-June) of **current year**

2. **Generates consolidated department report** using:
   ```bash
   python3 consumption_report.py --half_year <1 or 2> <year> --Department
   ```
   - This creates ONE report with ALL departments aggregated

3. **On Success**:
   - Sends one email to DevOps team with report attached
   - Email subject includes period (e.g., "H1 2025 (Jan-Jun)")

4. **On Failure**:
   - Sends one failure notification email to DevOps team
   - Includes error details and console output link
   - No report sent to users

## grace_periods.xlsx File Format

The Excel file should have these columns:

| Department | mail                    | start      | end        |
|------------|-------------------------|------------|------------|
| hpc        | admin@example.com       | 01.11.2025 | 07.11.2025 |
| research   | research@example.com    | 15.11.2025 | 25.11.2025 |
| engineering| engineering@example.com | 01.07.2025 | 14.07.2025 |

**Required columns for Jenkins:**
- `Department`: Department/project name
- `mail`: Email address to send report to

**Optional columns (used by Python scripts only):**
- `start`: Grace period start date
- `end`: Grace period end date

## Testing

### Test Monthly Reports Manually
You can trigger the monthly pipeline manually without waiting for the schedule:

1. Go to Jenkins job page (`Monthly-Consumption-Reports`)
2. Click "Build Now"
3. Check "Console Output" for progress

### Test Half-Year Reports Manually
You can trigger the half-year pipeline manually:

1. Go to Jenkins job page (`HalfYear-Department-Reports`)
2. Click "Build Now"
3. Check "Console Output" for progress

### Test with Different Month (Monthly Reports)
The pipeline automatically generates reports for the previous month. To test with a specific month, you can:

**Option 1**: Temporarily modify the date calculation in the Jenkinsfile:
```groovy
// Replace the date calculation lines with hardcoded values
def previousMonth = "11"  // November
def reportYear = "2025"
```

**Option 2**: Test the Python script directly from command line:
```bash
   cd /var/lib/jenkins/workspace/Monthly-Consumption-Reports/consumption_report
```

## Troubleshooting

### Pipeline doesn't trigger automatically
- Check Jenkins system clock: `date`
- Verify cron expression in Jenkinsfile
- Check Jenkins logs: Manage Jenkins → System Log

### Email not sending
- Verify Email Extension Plugin is installed
- Check SMTP configuration in Jenkins
- Test email settings in Jenkins System Configuration
- Check Jenkins user has internet access

### Python errors
- Check virtual environment is created: `ls ${WORKSPACE}/consumption_report/env`
- Verify requirements are installed: `${PYTHON_ENV} -m pip list`
- Check Python version: `${PYTHON_ENV} --version`

### Permission errors
- Ensure Jenkins user has read access to the repository
- Ensure Jenkins user can write to `~/consumption_report/` directory
- Check file permissions: `ls -la`

## Manual Commands for Jenkins User

If you need to set up manually for the Jenkins user:

```bash
# Switch to Jenkins user
sudo su - jenkins

# Navigate to workspace
cd /var/lib/jenkins/workspace/Automated-Consumption-Reports/consumption_report

# Create virtual environment
python3 -m venv env

# Install requirements
env/bin/pip install -r requirements.txt

# Test report generation (example for November 2025)
env/bin/python3 consumption_report.py --month 11 2025 --Project hpc
```

## Report Timing

### Monthly Project Reports

**Important**: The pipeline runs on the **1st of each month** but generates reports for the **previous month**.

| Run Date       | Report Month  | Reason                                    |
|----------------|---------------|-------------------------------------------|
| January 1      | December      | Previous year's December                  |
| February 1     | January       | Current year's January                    |
| September 1    | August        | Current year's August                     |
| December 1     | November      | Current year's November                   |

This timing makes sense because:
- The 1st of the month is when the previous month's data is complete
- Gives time for all systems to finalize resource usage data
- Reports are delivered at the start of the new billing cycle

### Half-Year Department Reports

**Important**: The pipeline runs **twice per year** and reports the **completed half-year**.

| Run Date   | Report Period | Description                    |
|------------|---------------|--------------------------------|
| January 1  | H2 (Jul-Dec)  | Previous year's second half    |
| July 1     | H1 (Jan-Jun)  | Current year's first half      |

Examples:
- **January 1, 2026** → Reports July-December 2025
- **July 1, 2026** → Reports January-June 2026

This timing ensures:
- Complete data for the entire half-year period
- Alignment with financial/billing cycles
- Time for systems to finalize all resource usage data
```

## Security Notes

- The `disableConcurrentBuilds()` option ensures only one build runs at a time
- Each department's report overwrites the previous one (by design)
- Email credentials should be stored securely in Jenkins credentials store
- Consider using Jenkins secrets for sensitive information

## Maintenance

### Update Python Dependencies
Both pipelines automatically update dependencies on each run. To force an update:
1. Update `requirements.txt` in the repository
2. Commit and push changes
3. Next run will install updated packages

### Add/Remove Departments (Monthly Reports Only)
Simply edit the `grace_periods.xlsx` file:
- **Add row**: Department will be processed automatically
- **Remove row**: Department will be skipped
- Changes take effect on next scheduled run

**Note**: Half-year reports include ALL departments automatically, no configuration needed.

### Change Schedules

#### Monthly Reports
Edit the cron expression in `Jenkinsfile.monthly`:
```groovy
triggers {
    cron('0 8 1 * *')  // Modify this line
}
```

#### Half-Year Reports
Edit the cron expression in `Jenkinsfile.halfyear`:
```groovy
triggers {
    cron('0 11 1 1,7 *')  // Modify this line
}
```

Commit and push changes after modifying.

---

## Summary: Key Differences Between Pipelines

| Feature | Monthly Project Reports | Half-Year Department Reports |
|---------|------------------------|------------------------------|
| **Jenkinsfile** | `Jenkinsfile.monthly` | `Jenkinsfile.halfyear` |
| **Schedule** | 1st of every month, 9:00 AM | Jan 1 & Jul 1, 11:00 AM |
| **Report Type** | Project reports (per department) | Department report (all consolidated) |
| **Command** | `--month <M> <YEAR> --Project <dept>` | `--half_year <1|2> <YEAR> --Department` |
| **Input Source** | `grace_periods.xlsx` | Automatic (all departments) |
| **Recipients** | Individual users per department | DevOps team only |
| **Email Count** | One per department + one summary | One (success or failure) |
| **Monitoring** | Summary email with stats to DevOps | Included in success/failure email |
| **Error Handling** | Continue processing other departments | Stop and notify DevOps |
| **Output File** | `consumption_report_projects.xlsx` | `consumption_report_departments.xlsx` |
| **Report Period** | Previous month | Previous half-year |

---

## Quick Setup Checklist

- [ ] Jenkins server with required plugins installed
- [ ] Two pipeline jobs created (`Monthly-Consumption-Reports` and `HalfYear-Department-Reports`)
- [ ] Both jobs pointing to correct repository and branch
- [ ] Email (SMTP) configured in Jenkins
- [ ] `DEVOPS_EMAIL` variable set correctly in both Jenkinsfiles
- [ ] `grace_periods.xlsx` file exists in repository with correct columns
- [ ] Python 3 installed on Jenkins server
- [ ] Test both pipelines with "Build Now"
- [ ] Verify emails are received correctly
- [ ] Check cron triggers are registered in Jenkins
