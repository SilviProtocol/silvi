# CSV File Versioning Guide

THis guide explains how to track versions of your CSV files by converting them to Google Sheets and using the built-in versioning system.

## Why Convert CSV to Google Sheets?

Your versioning system is designed to work with Google Sheets, which provides:
- Automatic version tracking with metadata
- Browser-based viewing and editing
- Change history and snapshots
- Integration with your ontology generation pipeline
- Handles large files by splitting across multiple worksheets

## Quick Start

### Option 1: Using the Web UI

1. **Start your application**
   ```bash
   python app.py
   ```

2. **Navigate to Version Management**
   - Open: `http://localhost:5001/version-management`

3. **Go to the "Import CSV" tab**
   - Click on the **"Import CSV"** tab at the top

4. **Fill in the form:**
   - **CSV File Paths**: Full path to your CSV file (e.g., `/path/to/data.csv`)
   - **Spreadsheet Name**: Name for the Google Sheet (e.g., "Biodiversity Data 2025")
   - **Initial Version**: Version number (default: `1.0.0`)
   - **Author**: Your name (optional)
   - **Description**: Description of the data (optional)

5. **Click "Import CSV"**
   -Progress will be shown during import
   - You'll get a link to the new spreadsheet when complete

6. **Manage versions:**   
   - Use "Find Spreadsheet" to locate your imported sheet
   - Update version when you make changes
   - Create snapshots for major milestones

### Option 2: Using the Command Line

```bash
# Basic import
python csv_importer.py /path/to/data.csv --name "My Data Sheet"

# With version and author
python csv_importer.py /path/to/data.csv \
   --name "Species Data" \
   --version 1.0.0 \
   --author "John Doe" \
   --description "2025 field survey data"

# With custom service account
python csv_importer.py /path/to/data.csv \
   --name "Data" \
   --service-account ./service_account.json
```

## Handling Large CSV Files

The system automatically handles large CSV files;

### Automatic Splitting
- **Threshold**: Files with more than 45,000 rows
- **Action**: Automatically split across multiple worksheets
- **Naming**: `data_part1`, `data_part2`, etc.
- **Batch processing**: Writes in batches of 5,000 rows for efficiency

## Example output
```
Found CSV with 150,000 rows
Creating 4 worksheets...
   -data_part1 (45,000 rows)
   -data_part2 (45,000 rows)
   -data_part3 (45,000 rows)
   -data_part4 (15,000 rows)
Import complete!
```

## Version Mangement Workflow

### 1. Initial Import
```bash
python csv_importer.py biodiversity_data.csv \
   --name "Biodiversity Dataset" \
   --version 1.0.0 \
   --author "Research Team"
```

Result: Google Sheet created with version `1.0.0`

### 2. Make changes
- Edit data in Google Sheets
- Add/remove rows
- Updata values

### 3. Update Version
Using the web UI at `/version-management`:

1. **Find your spreadsheet** (by name or ID)
2. Go to **"Update Version"** tab
3. Fill in:
   - **New Version** `1.0.1` (or `1.1.0` for minor changes, `2.0.0` for major)
   - **Modified By**: Your name
   - **Changelog**: "Added 50 new species for fieldwork"
4. Click **"Update Version"**

### 4. Create Snapshots (Optional)
Before major changes, create a snapshot:

1. Go to **"Create Snapshot"** tab
2. Enter version name: `v1.0.1-backup`
3. Click **"Create Snapshot"**

This creates a frozen copy you can reference later.

## Version Numbering (Semantic Versioning)

Follow this convention:

```
major.minor.patch
  │     │     │
  │     │     └─ Bug fixes, small corrections (1.0.0 → 1.0.1)
  │     └─────── New features, added data (1.0.0 → 1.1.0)
  └───────────── Breaking changes, major restructuring (1.0.0 → 2.0.0)
```

### Examples:
- `1.0.0` -> `1.0.1`: Fixed 5 typos in species names
- `1.0.0` -> `1.1.0`: Added new column for habitat data
- `1.0.0` -> `2.0.0`: Completely restructured taxonomy

## Metadata Storage

Every versioned spreadsheet has a `metadata` worksheet with:

```
version              | 1.0.1
version_date         | 2025-05-19T20:24:01
created_by           | Research Team
creation_date        | 2025-05-14T12:00:00
description          | 2025 biodiversity survey data 
last_modified_by     | John Doe
last_modified_date   | 2025-05-19T20:24:01
changelog            | 2025-05-19 - v1.0.1: Added 50 species
                     | 2025-05-16 - v1.0.0: Initial import
```

## API Endpoints

### Import CSV
```bash
POST /import-csv
Content-Type: multipart/form-data

csv_file_path: /path/to/file.csv
spreadsheet_name: My Data
version: 1.0.0
author: John Doe
description: Survey data
```

### Get Spreadhseet Metadata
```bash
GET /spreadsheet-metadata?spreadsheet_name=My Data
```

### Update Version
```bash
POST /update-spreadsheet-version
Content-Type: multipart/form-data

spreadshet_name: My Data
new_version: 1.0.1
modified_by: John Doe
changelog: Fixed data errors
```

### Create Snapshot
```bash
POST /create-version-snapshot
Content-Type: multipart/form-data

spreadsheet_name: My Data
version_name: v1.0.1-backup
```

## Best Practices

### 1. Regular Version Updates
- Update version after each significant change
- Don't batch multiple change into one version
- Use descriptive changelog entries

### 2. Snapshots for Safety
Create snapshots before:
- Major data reorganization
- Bulk deletions
- Schema changes
- Sharing with external collaborators

### 3. Descriptive Naming
```
Good: "2025 Bird Species Survey - Eastern Region"
Bad: "data_final_v2_FINAL"
```

### 4. Consistent Authorship
- Always fill in "Modified By" field
- Use full names for accountability
- Keep author names consistent

### 5. Detailed Changelogs
```
Good: "Added 127 new species records from May fieldwork.
       Updated GPS coordinates for 43 existing records.
       Fixed taxonomy for genus Quercus."

Bad: "Updates"
```

## Troubleshooting

### Import Fails: "File Not Found"
- Check the file path is absolute (not relative)
- Verify file exists: `ls -l /path/to/file.csv`
- Check file permissions: `chmod 644 /path/to/file.csv`

### Import Fails: "Google Sheets Not Available"
- Verify service account JSON is configures
- Check environment variable: `echo $GOOGLE_SERVICE_ACCOUNT_JSON`
- Restart the application

### Large File Import is Slow
- This is normal for files > 50,000 rows
- Progress is shown during import
- Typically: 10,000 rows/minute

### Can't Find Spreadsheet in Version Mangement
- Ensure spreadsheet is shared with service account email
- Check spreadsheet name matches exactly (case-sensitive)
- Try using Spreadsheet ID instead of name

##
            