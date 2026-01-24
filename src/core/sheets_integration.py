import os
import json
import gspread
import datetime
from google.oauth2.service_account import Credentials

class SheetsIntegration:
    """
    A class to handle Google Sheets integration with the application.
    Enhanced with versioning and metadata capabilities.
    """
    
    def __init__(self, service_account_file=None, service_account_json=None):
        """
        Initialize the Google Sheets integration.
        
        Args:
            service_account_file (str, optional): Path to the service account JSON file.
            service_account_json (str, optional): JSON string of the service account credentials.
        """
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        try:
            # Try to use service account file first
            if service_account_file and os.path.exists(service_account_file):
                self.credentials = Credentials.from_service_account_file(
                    service_account_file, scopes=self.scopes
                )
            # Otherwise, try to use service account JSON string from environment variable
            elif service_account_json:
                service_account_info = json.loads(service_account_json)
                self.credentials = Credentials.from_service_account_info(
                    service_account_info, scopes=self.scopes
                )
            # Otherwise, try to get from environment variable
            elif os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'):
                service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
                self.credentials = Credentials.from_service_account_info(
                    service_account_info, scopes=self.scopes
                )
            else:
                raise ValueError("No service account credentials provided.")
                
            # Create the gspread client
            self.client = gspread.authorize(self.credentials)
            self.initialized = True
        except Exception as e:
            print(f"Error initializing Google Sheets integration: {str(e)}")
            self.initialized = False
    
    def is_initialized(self):
        """Check if the integration is properly initialized."""
        return self.initialized
    
    def open_spreadsheet(self, spreadsheet_id=None, spreadsheet_name=None):
        """
        Open a Google Sheet by ID or name.
        
        Args:
            spreadsheet_id (str, optional): The ID of the spreadsheet.
            spreadsheet_name (str, optional): The name of the spreadsheet.
            
        Returns:
            gspread.Spreadsheet: The spreadsheet object.
        """
        if not self.initialized:
            raise ValueError("Google Sheets integration not properly initialized.")
            
        try:
            if spreadsheet_id:
                return self.client.open_by_key(spreadsheet_id)
            elif spreadsheet_name:
                return self.client.open(spreadsheet_name)
            else:
                raise ValueError("Either spreadsheet_id or spreadsheet_name must be provided.")
        except Exception as e:
            raise ValueError(f"Error opening spreadsheet: {str(e)}")
    
    def get_worksheet_data(self, spreadsheet, worksheet_name=None, worksheet_index=0):
        """Get all data from a worksheet as a list of dictionaries."""
        try:
            # Get the worksheet
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(worksheet_index)
            
            # Get all values
            all_values = worksheet.get_all_values()
            
            # Check if we have data
            if not all_values or len(all_values) <= 1:
                return []
            
            # Convert to dictionaries
            headers = all_values[0]
            return [dict(zip(headers, row)) for row in all_values[1:]]
            
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(f"Error getting worksheet data: {worksheet_name} - Worksheet not found")
        except gspread.exceptions.APIError as e:
            raise ValueError(f"Error getting worksheet data: {worksheet_name} - API error: {str(e)}")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            raise ValueError(f"Error getting worksheet data: {worksheet_name} - {str(e)}\nDetails: {error_details}")
    
    def get_spreadsheet_metadata(self, spreadsheet):
        """
        Extract metadata from a Google Spreadsheet.
        
        Args:
            spreadsheet (gspread.Spreadsheet): The spreadsheet object.
            
        Returns:
            dict: Metadata about the spreadsheet including version information.
        """
        try:
            # Basic spreadsheet info
            metadata = {
                "title": spreadsheet.title,
                "id": spreadsheet.id,
                "created_at": None,  # Will try to get from Drive API
                "last_updated": None,  # Will try to get from Drive API
                "worksheets": [],
                "version_info": {}
            }
            
            # Get worksheet info with actual data dimensions
            for worksheet in spreadsheet.worksheets():
                # Get actual data to count real rows and columns
                all_values = worksheet.get_all_values()

                # Count non-empty rows (excluding header)
                actual_rows = 0
                actual_cols = 0

                if all_values:
                    # Count rows with at least one non-empty cell
                    actual_rows = sum(1 for row in all_values if any(cell.strip() for cell in row))
                    # Get max column count from non-empty rows
                    if actual_rows > 0:
                        actual_cols = max(len([cell for cell in row if cell.strip()]) for row in all_values if any(cell.strip() for cell in row))

                worksheet_meta = {
                    "title": worksheet.title,
                    "id": worksheet.id,
                    "row_count": actual_rows,
                    "col_count": actual_cols
                }
                metadata["worksheets"].append(worksheet_meta)
            
            # Try to get version info if available in a metadata worksheet
            try:
                if "metadata" in [ws.title for ws in spreadsheet.worksheets()]:
                    metadata_sheet = spreadsheet.worksheet("metadata")
                    metadata_values = metadata_sheet.get_all_values()
                    
                    if metadata_values and len(metadata_values) > 1:
                        # Convert metadata to dictionary
                        metadata_keys = [row[0] for row in metadata_values if len(row) > 0]
                        metadata_values = [row[1] if len(row) > 1 else "" for row in metadata_values]
                        version_info = dict(zip(metadata_keys, metadata_values))
                        
                        # Extract version info
                        metadata["version_info"] = {
                            "version": version_info.get("version", "N/A"),
                            "version_date": version_info.get("version_date", "N/A"),
                            "created_by": version_info.get("created_by", "N/A"),
                            "description": version_info.get("description", ""),
                            "last_modified_by": version_info.get("last_modified_by", "N/A"),
                            "changelog": version_info.get("changelog", "")
                        }
            except Exception as e:
                print(f"Error getting version info: {str(e)}")
            
            # Try to access Google Drive API to get file metadata
            try:
                # This requires drive scope and may need additional permissions
                file_metadata = self.client.drive.files().get(
                    fileId=spreadsheet.id, 
                    fields="createdTime,modifiedTime,owners"
                ).execute()
                
                if file_metadata:
                    metadata["created_at"] = file_metadata.get("createdTime")
                    metadata["last_updated"] = file_metadata.get("modifiedTime")
                    metadata["owners"] = [owner.get("displayName") for owner in file_metadata.get("owners", [])]
            except Exception as e:
                print(f"Warning: Could not retrieve file metadata from Drive API: {str(e)}")
                # Fall back to current time
                current_time = datetime.datetime.now().isoformat()
                metadata["last_updated"] = current_time
            
            return metadata
            
        except Exception as e:
            print(f"Error getting spreadsheet metadata: {str(e)}")
            return {"error": str(e)}
    
    def create_versioned_spreadsheet(self, title, version="1.0.0", author=None, description=None):
        """
        Create a new Google Sheet with versioning metadata.
        
        Args:
            title (str): The title of the new spreadsheet.
            version (str): Version number (semantic versioning recommended).
            author (str): Name of the author.
            description (str): Description of the spreadsheet.
            
        Returns:
            gspread.Spreadsheet: The newly created spreadsheet.
        """
        try:
            # Create the spreadsheet
            spreadsheet = self.client.create(title)
            
            # Create a metadata worksheet
            metadata_sheet = spreadsheet.add_worksheet(title="metadata", rows=10, cols=2)
            
            # Current time in ISO format
            current_time = datetime.datetime.now().isoformat()
            
            # Metadata rows
            metadata_rows = [
                ["version", version],
                ["version_date", current_time],
                ["created_by", author or "Unknown"],
                ["creation_date", current_time],
                ["description", description or ""],
                ["last_modified_by", author or "Unknown"],
                ["last_modified_date", current_time],
                ["changelog", f"Initial version {version} created on {current_time}"]
            ]
            
            # Update the metadata worksheet
            metadata_sheet.update("A1:B" + str(len(metadata_rows)), metadata_rows)
            
            return spreadsheet
            
        except Exception as e:
            raise ValueError(f"Error creating versioned spreadsheet: {str(e)}")
    
    def update_spreadsheet_version(self, spreadsheet, new_version, modified_by, changelog=None):
        """
        Update the version information of a spreadsheet.
        
        Args:
            spreadsheet (gspread.Spreadsheet): The spreadsheet object.
            new_version (str): New version number.
            modified_by (str): Name of person making the change.
            changelog (str, optional): Notes about changes in this version.
            
        Returns:
            bool: Success or failure.
        """
        try:
            # Get the metadata worksheet
            try:
                metadata_sheet = spreadsheet.worksheet("metadata")
            except gspread.exceptions.WorksheetNotFound:
                # Create metadata sheet if it doesn't exist
                metadata_sheet = spreadsheet.add_worksheet(title="metadata", rows=10, cols=2)
                
                # Initialize metadata if it's new
                current_time = datetime.datetime.now().isoformat()
                metadata_rows = [
                    ["version", "1.0.0"],
                    ["version_date", current_time],
                    ["created_by", modified_by or "Unknown"],
                    ["creation_date", current_time],
                    ["description", ""],
                    ["last_modified_by", ""],
                    ["last_modified_date", ""],
                    ["changelog", ""]
                ]
                metadata_sheet.update("A1:B" + str(len(metadata_rows)), metadata_rows)
            
            # Current time in ISO format
            current_time = datetime.datetime.now().isoformat()
            
            # Update version info
            metadata_sheet.update("B1", new_version)  # Version
            metadata_sheet.update("B2", current_time)  # Version date
            metadata_sheet.update("B6", modified_by or "Unknown")  # Last modified by
            metadata_sheet.update("B7", current_time)  # Last modified date
            
            # Update changelog if provided
            if changelog:
                # Get existing changelog
                try:
                    existing_changelog = metadata_sheet.acell("B8").value or ""
                    updated_changelog = f"{current_time} - v{new_version}: {changelog}\n" + existing_changelog
                    metadata_sheet.update("B8", updated_changelog)
                except:
                    metadata_sheet.update("B8", f"{current_time} - v{new_version}: {changelog}")
            
            return True
            
        except Exception as e:
            print(f"Error updating spreadsheet version: {str(e)}")
            return False
    
    def create_spreadsheet(self, title):
        """
        Create a new Google Sheet (original method preserved for compatibility).
        
        Args:
            title (str): The title of the new spreadsheet.
            
        Returns:
            gspread.Spreadsheet: The newly created spreadsheet.
        """
        try:
            return self.client.create(title)
        except Exception as e:
            raise ValueError(f"Error creating spreadsheet: {str(e)}")
    
    def append_rows(self, spreadsheet, worksheet_index=0, worksheet_name=None, values=None):
        """
        Append rows to a worksheet.
        
        Args:
            spreadsheet (gspread.Spreadsheet): The spreadsheet object.
            worksheet_index (int, optional): The index of the worksheet (0-based).
            worksheet_name (str, optional): The name of the worksheet.
            values (list): List of lists with the values to append.
            
        Returns:
            dict: The response from the API.
        """
        try:
            # Get the worksheet by index or name
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(worksheet_index)
                
            # Append the rows
            return worksheet.append_rows(values)
        except Exception as e:
            raise ValueError(f"Error appending rows: {str(e)}")
    
    def update_values(self, spreadsheet, range_name, values, worksheet_index=0, worksheet_name=None):
        """
        Update values in a specific range.
        
        Args:
            spreadsheet (gspread.Spreadsheet): The spreadsheet object.
            range_name (str): The A1 notation of the range to update (e.g., 'A1:B2').
            values (list): List of lists with the values to update.
            worksheet_index (int, optional): The index of the worksheet (0-based).
            worksheet_name (str, optional): The name of the worksheet.
            
        Returns:
            dict: The response from the API.
        """
        try:
            # Get the worksheet by index or name
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(worksheet_index)
                
            # Update the values
            return worksheet.update(range_name, values)
        except Exception as e:
            raise ValueError(f"Error updating values: {str(e)}")
    
    def create_version_snapshot(self, spreadsheet, version_name):
        """
        Create a snapshot of the current spreadsheet as a new spreadsheet with version info.
        
        Args:
            spreadsheet (gspread.Spreadsheet): The source spreadsheet.
            version_name (str): Name of the version (e.g., "v1.2.3").
            
        Returns:
            gspread.Spreadsheet: The newly created snapshot spreadsheet.
        """
        try:
            # Get current time
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Create a new spreadsheet for the snapshot
            snapshot_title = f"{spreadsheet.title} - {version_name} ({current_time})"
            snapshot = self.client.create(snapshot_title)
            
            # Get metadata if available
            try:
                metadata = self.get_spreadsheet_metadata(spreadsheet)
            except:
                metadata = {"worksheets": [], "version_info": {}}
            
            # Create a metadata worksheet in the snapshot
            metadata_sheet = snapshot.add_worksheet(title="metadata", rows=15, cols=2)
            
            # Update with snapshot metadata
            metadata_rows = [
                ["original_spreadsheet_id", spreadsheet.id],
                ["original_spreadsheet_title", spreadsheet.title],
                ["snapshot_version", version_name],
                ["snapshot_date", current_time],
                ["original_version", metadata.get("version_info", {}).get("version", "Unknown")],
                ["description", metadata.get("version_info", {}).get("description", "")],
                ["changelog", metadata.get("version_info", {}).get("changelog", "")]
            ]
            metadata_sheet.update("A1:B" + str(len(metadata_rows)), metadata_rows)
            
            # Copy all worksheets from the original spreadsheet
            for worksheet_meta in metadata.get("worksheets", []):
                if worksheet_meta["title"] != "metadata":  # Skip metadata worksheet
                    try:
                        # Get original worksheet
                        orig_worksheet = spreadsheet.worksheet(worksheet_meta["title"])
                        values = orig_worksheet.get_all_values()
                        
                        if values:
                            # Create new worksheet in snapshot
                            new_worksheet = snapshot.add_worksheet(
                                title=worksheet_meta["title"],
                                rows=max(10, len(values) + 5),
                                cols=max(10, worksheet_meta["col_count"])
                            )
                            
                            # Copy data
                            if len(values) > 0:
                                new_worksheet.update("A1", values)
                    except Exception as ws_error:
                        print(f"Error copying worksheet {worksheet_meta['title']}: {str(ws_error)}")
            
            # Delete the default "Sheet1" if it exists
            try:
                default_sheet = snapshot.worksheet("Sheet1")
                snapshot.del_worksheet(default_sheet)
            except:
                pass
                
            return snapshot
            
        except Exception as e:
            raise ValueError(f"Error creating version snapshot: {str(e)}")

# Example usage
if __name__ == "__main__":
    # For testing purposes
    sheets = SheetsIntegration(service_account_file="service_account.json")
    if sheets.is_initialized():
        # Create a versioned spreadsheet
        spreadsheet = sheets.create_versioned_spreadsheet(
            title="Biodiversity Data - 2025 Edition", 
            version="1.0.0", 
            author="Research Team",
            description="Comprehensive biodiversity data for ontology generation"
        )
        
        print(f"Created new versioned spreadsheet: {spreadsheet.title} (ID: {spreadsheet.id})")
        
        # Get metadata
        metadata = sheets.get_spreadsheet_metadata(spreadsheet)
        print(f"Spreadsheet metadata: {json.dumps(metadata, indent=2)}")