# Changelog

## [Unreleased] - 2025-10-08

### Added
- **Automatic Schema Format Detection**: System now automatically detects and handles three data formats:
  - Direct Schema Format: Column names as field definitions
  - Transposed Format: Field names in rows (single column with 120+ rows)
  - MVP Format: Traditional metadata sheet with specific columns
- **Flexible Sheet Recognition**:
  - "species" sheets recognized as MVP files
  - "optionset" sheets recognized as enumeration data
  - "metadata" sheets skipped (used for version tracking only)
- **New Analysis Method**: `analyze_direct_schema()` handles column-based and transposed schemas
- **Comprehensive README.md**: Full project documentation with setup, usage, and API reference
- **Enhanced Documentation**: Updated HTML documentation with schema format examples
- **Troubleshooting Guide**: New section covering common issues and their resolutions

### Fixed
- **"Page Not Found" Alert**: Browser/extension requests (favicon.ico, .well-known/) no longer trigger error messages
- **Incorrect Row/Column Counts**: Metadata now shows actual data dimensions instead of allocated sheet size (1000×26)
- **Small Ontology Files**: Transposed schemas (120 rows × 1 column) now properly processed
- **Missing Method Errors**: Added compatibility fields (`ontology_class`, `required`, `range_class`) to field_info structure
- **Google Sheets Import**: Preview endpoint corrected from `/preview-dynamic-ontology` to `/preview-multi-sheet-ontology`

### Changed
- **Sheet Metadata Calculation**: Now counts only non-empty rows and columns
- **Error Handler**: 404 errors from common browser requests no longer flash messages to users
- **Field Analysis**: Direct schema format automatically infers data types and categories from field names
- **Documentation Structure**: Added "Recent Improvements" section and "Supported Sheet Formats" guide

### Technical Details

#### Files Modified
- `app.py`: Updated 404 error handler to ignore browser/extension requests
- `sheets_integration.py`: Fixed metadata calculation to show actual data dimensions
- `multi_sheet_biodiversity_generator.py`:
  - Added `analyze_direct_schema()` method
  - Added `_infer_data_type_from_name()` helper method
  - Updated sheet recognition to include "species" and skip "metadata"
  - Fixed transposed format detection
- `templates/index.html`: Removed "Create Ontology from File" section
- `templates/import_sheets.html`: Corrected preview endpoint URL
- `templates/documentation.html`: Added schema format guide and updated troubleshooting
- `README.md`: New comprehensive project documentation

#### New Features in Detail

**Transposed Format Detection**:
```python
# Detects when schema has many rows in single column
if len(field_names) == 1 and len(rows) > 10:
    # Extract field names from rows
    field_names = [row[column_name].strip() for row in rows]
```

**Smart Field Categorization**:
- Automatically categorizes 120+ fields into 8 ontology classes
- Infers data types (string, int, float, date, boolean) from field names
- Links fields to option sets when available

**Quality Assessment**:
- Completeness score calculation
- Taxonomic/Geographic/Ecological completeness checking
- Enumeration coverage tracking

---

## Known Issues

None currently reported.

---

## Migration Guide

### For Existing Users

If you have existing spreadsheets:

1. **No changes required** - The system auto-detects your format
2. **Transposed data** (field names in rows) - Works automatically now
3. **Direct schema** (field names as columns) - Already supported
4. **MVP format** - Continue using as before

### Testing

After updating, verify:
1. ✅ Import from Google Sheets works without alerts
2. ✅ Metadata shows correct row/column counts
3. ✅ Generated ontology file is appropriately sized (50-100+ KB for 120 fields)
4. ✅ Check terminal logs for "Detected transposed format" or "Detected direct schema format"

---

## Future Enhancements

### Planned Features
- [ ] Support for additional data sources (MongoDB, MySQL)
- [ ] Visual ontology editor
- [ ] Batch processing improvements
- [ ] Enhanced quality metrics and validation
- [ ] Real-time collaboration features
- [ ] API documentation with Swagger/OpenAPI
- [ ] Docker containerization
- [ ] CI/CD pipeline setup

### Under Consideration
- GraphQL API endpoint
- WebSocket support for real-time updates
- Machine learning-based field categorization
- Multi-language support
- Cloud deployment templates (AWS, Azure, GCP)

---

## Contributors

Thank you to everyone who contributed to this release!

---

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the documentation at `/documentation`
- Review troubleshooting guide in README.md
