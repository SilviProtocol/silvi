#!/usr/bin/env python3
"""CSV to Google Sheets importer with automatic versioning.

This module provides functionality to import large CSV files into Google Sheets
with automatic versioning support, handling files that exceed Google Sheets
limits by splitting them across multiple worksheets.
"""

import os
import csv
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from sheets_integration import SheetsIntegration


class CSVImporter:
    """Handles importing CSV files to Google Sheets with versioning.

    This class manages the import of CSV files, including large files that
    need to be split across multiple worksheets, and initializes versioning
    metadata automatically.

    Attributes:
        sheets: SheetsIntegration instance for Google Sheets operations.
        batch_size: Number of rows to write in each batch operation.
        max_rows_per_sheet: Maximum rows per worksheet (Google Sheets limit).
    """

    def __init__(self, sheets_integration: SheetsIntegration):
        """Initialize the CSV importer.

        Args:
            sheets_integration: Initialized SheetsIntegration instance.
        """
        self.sheets = sheets_integration
        self.batch_size = 5000  # Rows per batch write
        self.max_rows_per_sheet = 45000  # Leave buffer for Google Sheets limit

    def count_csv_rows(self, csv_path: str) -> int:
        """Count total rows in a CSV file.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            Total number of data rows (excluding header).

        Raises:
            FileNotFoundError: If the CSV file doesn't exist.
            IOError: If there's an error reading the file.
        """
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found: {csv_path}")

            with open(csv_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f) - 1  # Exclude header

        except FileNotFoundError:
            raise
        except Exception as e:
            raise IOError(f"Error reading CSV file: {str(e)}")

    def import_csv(self, csv_path: str, spreadsheet_name: str,
                   version: str = "1.0.0", author: Optional[str] = None,
                   description: Optional[str] = None) -> Dict[str, Any]:
        """Import a CSV file to Google Sheets with versioning.

        Automatically handles large files by splitting across multiple
        worksheets if needed.

        Args:
            csv_path: Path to the CSV file to import.
            spreadsheet_name: Name for the new Google Sheet.
            version: Initial version number (default: "1.0.0").
            author: Name of the person importing the file.
            description: Description of the spreadsheet content.

        Returns:
            Dictionary containing import results with keys:
                - spreadsheet_id: The Google Sheets ID
                - spreadsheet_url: Direct link to the sheet
                - rows_imported: Total number of rows imported
                - worksheets_created: Number of worksheets created
                - version: Version number assigned

        Raises:
            FileNotFoundError: If CSV file doesn't exist.
            ValueError: If spreadsheet creation or import fails.
        """
        try:
            print(f"Starting import of {csv_path}...")

            # Validate file exists
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found: {csv_path}")

            # Count rows
            total_rows = self.count_csv_rows(csv_path)
            print(f"Total rows to import: {total_rows:,}")

            # Determine if we need multiple worksheets
            needs_splitting = total_rows > self.max_rows_per_sheet

            if needs_splitting:
                print(f"File exceeds {self.max_rows_per_sheet:,} rows.")
                print("Will split across multiple worksheets...")
                return self._import_large_csv(
                    csv_path, spreadsheet_name, total_rows,
                    version, author, description
                )
            else:
                return self._import_single_worksheet(
                    csv_path, spreadsheet_name, total_rows,
                    version, author, description
                )

        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Error during CSV import: {str(e)}")

    def _import_single_worksheet(self, csv_path: str, spreadsheet_name: str,
                                 total_rows: int, version: str,
                                 author: Optional[str],
                                 description: Optional[str]) -> Dict[str, Any]:
        """Import CSV into a single worksheet.

        Args:
            csv_path: Path to CSV file.
            spreadsheet_name: Name for the spreadsheet.
            total_rows: Total number of rows.
            version: Version number.
            author: Author name.
            description: Description text.

        Returns:
            Import results dictionary.

        Raises:
            ValueError: If import fails.
        """
        try:
            # Create versioned spreadsheet
            print(f"Creating spreadsheet '{spreadsheet_name}'...")
            spreadsheet = self.sheets.create_versioned_spreadsheet(
                title=spreadsheet_name,
                version=version,
                author=author or "CSV Importer",
                description=description or f"Imported from {os.path.basename(csv_path)}"
            )

            # Create data worksheet
            print("Creating data worksheet...")
            data_worksheet = spreadsheet.add_worksheet(
                title="data",
                rows=total_rows + 100,
                cols=50
            )

            # Import data
            self._write_csv_to_worksheet(
                csv_path, spreadsheet, data_worksheet.title, total_rows
            )

            # Delete default Sheet1
            self._delete_default_sheet(spreadsheet)

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"

            print(f"\nImport complete!")
            print(f"Spreadsheet URL: {spreadsheet_url}")

            return {
                'spreadsheet_id': spreadsheet.id,
                'spreadsheet_url': spreadsheet_url,
                'rows_imported': total_rows,
                'worksheets_created': 1,
                'version': version
            }

        except Exception as e:
            raise ValueError(f"Error importing to single worksheet: {str(e)}")

    def _import_large_csv(self, csv_path: str, spreadsheet_name: str,
                          total_rows: int, version: str,
                          author: Optional[str],
                          description: Optional[str]) -> Dict[str, Any]:
        """Import large CSV across multiple worksheets.

        Args:
            csv_path: Path to CSV file.
            spreadsheet_name: Name for the spreadsheet.
            total_rows: Total number of rows.
            version: Version number.
            author: Author name.
            description: Description text.

        Returns:
            Import results dictionary.

        Raises:
            ValueError: If import fails.
        """
        try:
            # Create versioned spreadsheet
            print(f"Creating spreadsheet '{spreadsheet_name}'...")
            spreadsheet = self.sheets.create_versioned_spreadsheet(
                title=spreadsheet_name,
                version=version,
                author=author or "CSV Importer",
                description=description or f"Imported from {os.path.basename(csv_path)}"
            )

            # Calculate number of worksheets needed
            num_worksheets = (total_rows // self.max_rows_per_sheet) + 1
            print(f"Creating {num_worksheets} worksheets...")

            # Import data across multiple worksheets
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader)

                worksheet_num = 1
                rows_processed = 0

                while rows_processed < total_rows:
                    # Create worksheet
                    worksheet_name = f"data_part{worksheet_num}"
                    print(f"\nCreating worksheet: {worksheet_name}")

                    worksheet = spreadsheet.add_worksheet(
                        title=worksheet_name,
                        rows=min(self.max_rows_per_sheet + 100, 50000),
                        cols=len(header) + 5
                    )

                    # Write header
                    worksheet.update('A1', [header])

                    # Write data in batches
                    batch = []
                    worksheet_rows = 0

                    for row in reader:
                        batch.append(row)
                        worksheet_rows += 1
                        rows_processed += 1

                        # Write batch when full or at worksheet limit
                        if len(batch) >= self.batch_size or \
                           worksheet_rows >= self.max_rows_per_sheet:
                            self.sheets.append_rows(
                                spreadsheet=spreadsheet,
                                worksheet_name=worksheet_name,
                                values=batch
                            )
                            batch = []
                            print(f"  Progress: {rows_processed:,}/{total_rows:,} "
                                  f"({rows_processed/total_rows*100:.1f}%)")

                        # Break if worksheet is full
                        if worksheet_rows >= self.max_rows_per_sheet:
                            break

                    # Write remaining rows in batch
                    if batch:
                        self.sheets.append_rows(
                            spreadsheet=spreadsheet,
                            worksheet_name=worksheet_name,
                            values=batch
                        )

                    worksheet_num += 1

            # Delete default Sheet1
            self._delete_default_sheet(spreadsheet)

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"

            print(f"\nImport complete!")
            print(f"Spreadsheet URL: {spreadsheet_url}")

            return {
                'spreadsheet_id': spreadsheet.id,
                'spreadsheet_url': spreadsheet_url,
                'rows_imported': total_rows,
                'worksheets_created': num_worksheets,
                'version': version
            }

        except Exception as e:
            raise ValueError(f"Error importing large CSV: {str(e)}")

    def _write_csv_to_worksheet(self, csv_path: str, spreadsheet,
                                worksheet_name: str, total_rows: int) -> None:
        """Write CSV data to a worksheet in batches.

        Args:
            csv_path: Path to CSV file.
            spreadsheet: Google Sheets spreadsheet object.
            worksheet_name: Name of the worksheet to write to.
            total_rows: Total number of rows for progress tracking.

        Raises:
            IOError: If there's an error reading the CSV.
            ValueError: If there's an error writing to the worksheet.
        """
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)

                # Read and write header
                header = next(reader)
                worksheet = spreadsheet.worksheet(worksheet_name)
                worksheet.update('A1', [header])

                # Write data in batches
                batch = []
                row_count = 0

                for row in reader:
                    batch.append(row)
                    row_count += 1

                    # Write when batch is full
                    if len(batch) >= self.batch_size:
                        self.sheets.append_rows(
                            spreadsheet=spreadsheet,
                            worksheet_name=worksheet_name,
                            values=batch
                        )
                        batch = []

                        # Progress update
                        if row_count % 10000 == 0:
                            progress = (row_count / total_rows) * 100
                            print(f"  Progress: {row_count:,}/{total_rows:,} "
                                  f"({progress:.1f}%)")

                # Write remaining rows
                if batch:
                    self.sheets.append_rows(
                        spreadsheet=spreadsheet,
                        worksheet_name=worksheet_name,
                        values=batch
                    )

                print(f"  Completed: {row_count:,} rows imported")

        except IOError as e:
            raise IOError(f"Error reading CSV file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error writing to worksheet: {str(e)}")

    def _delete_default_sheet(self, spreadsheet) -> None:
        """Delete the default 'Sheet1' if it exists.

        Args:
            spreadsheet: Google Sheets spreadsheet object.
        """
        try:
            default_sheet = spreadsheet.worksheet("Sheet1")
            spreadsheet.del_worksheet(default_sheet)
        except Exception:
            # Sheet doesn't exist or already deleted
            pass


def main():
    """Command-line interface for CSV import.

    Parses command-line arguments and executes the CSV import process.
    """
    parser = argparse.ArgumentParser(
        description='Import CSV files to Google Sheets with versioning',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic import
  python csv_importer.py data.csv --name "Biodiversity Data 2025"

  # With version and author
  python csv_importer.py data.csv --name "Species Data" --version 1.0.0 --author "John Doe"

  # With custom service account
  python csv_importer.py data.csv --name "Data" --service-account ./key.json
        """
    )

    parser.add_argument('csv_path', help='Path to CSV file to import')
    parser.add_argument('--name', required=True,
                       help='Name for the Google Sheet')
    parser.add_argument('--version', default='1.0.0',
                       help='Initial version number (default: 1.0.0)')
    parser.add_argument('--author',
                       help='Name of person importing the file')
    parser.add_argument('--description',
                       help='Description of the spreadsheet content')
    parser.add_argument('--service-account',
                       help='Path to service account JSON file')

    args = parser.parse_args()

    try:
        # Initialize Sheets integration
        print("Initializing Google Sheets integration...")
        sheets = SheetsIntegration(service_account_file=args.service_account)

        if not sheets.is_initialized():
            print("\nError: Could not initialize Google Sheets integration")
            print("Please ensure:")
            print("  1. Service account JSON is valid")
            print("  2. GOOGLE_SERVICE_ACCOUNT_JSON environment variable is set, OR")
            print("  3. Use --service-account flag with path to credentials")
            return 1

        # Create importer
        importer = CSVImporter(sheets)

        # Import CSV
        result = importer.import_csv(
            csv_path=args.csv_path,
            spreadsheet_name=args.name,
            version=args.version,
            author=args.author,
            description=args.description
        )

        # Print results
        print("\n" + "="*70)
        print("IMPORT SUCCESSFUL")
        print("="*70)
        print(f"Spreadsheet ID:  {result['spreadsheet_id']}")
        print(f"Spreadsheet URL: {result['spreadsheet_url']}")
        print(f"Rows imported:   {result['rows_imported']:,}")
        print(f"Worksheets:      {result['worksheets_created']}")
        print(f"Version:         {result['version']}")
        print("\nNext steps:")
        print("1. Open the spreadsheet URL above to view your data")
        print("2. Manage versions at: http://localhost:5001/version-management")
        print("3. Update version when you make changes to track history")

        return 0

    except FileNotFoundError as e:
        print(f"\nError: {str(e)}")
        return 1
    except ValueError as e:
        print(f"\nError: {str(e)}")
        return 1
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
