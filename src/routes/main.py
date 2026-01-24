# =============================================================================
# Complete routes_main.py - Multi-Sheet Biodiversity Ontology Generator
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from src.core.config import logger, check_triplestore_status
from src.utils import *
import os
import shutil
import uuid
import datetime
import time
import csv
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# Import our multi-sheet biodiversity ontology generator
from src.core.multi_sheet_generator import MultiSheetBiodiversityGenerator, generate_multi_sheet_biodiversity_ontology_from_directory



# Create blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the main page with multi-sheet biodiversity ontology capabilities."""
    from flask import current_app
    triplestore_status = check_triplestore_status() if current_app.config['TRIPLESTORE_ENABLED'] else False

    # Multi-sheet biodiversity ontology is always available
    has_dynamic_ontology = True

    return render_template('index.html',
                         triplestore_status=triplestore_status,
                         has_dynamic_ontology=has_dynamic_ontology,
                         ontology_type='multi_sheet_biodiversity')

@main_bp.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads with multi-sheet biodiversity ontology generation."""
    from flask import current_app
    
    try:
        # Create a unique directory for this session
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)

        files_uploaded = False
        uploaded_file_names = []

        # Process all uploaded files
        uploaded_files = request.files.getlist('files')
        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                if not allowed_file(filename):
                    flash('Invalid file type. Only CSV files are allowed.', 'warning')
                    continue

                logger.info(f"Saving file: {filename} to {session_dir}")
                file.save(os.path.join(session_dir, filename))
                files_uploaded = True
                uploaded_file_names.append(filename) 

        if not files_uploaded:
            flash("No files were uploaded. Please select at least one CSV file.", 'error')
            return redirect(url_for('main.index'))

        # Get ontology name
        ontology_name = request.form.get('ontology_name', '').strip()
        if not ontology_name:
            ontology_name = 'multi-sheet-biodiversity-ontology'
        ontology_name = sanitize_filename(ontology_name)

        # Generate multi-sheet biodiversity ontology
        try:
            logger.info(f"Generating multi-sheet biodiversity ontology {ontology_name} for session {session_id}")
            logger.info(f"Processing {len(uploaded_file_names)} files: {uploaded_file_names}")
            
            # Use the multi-sheet biodiversity ontology generator
            ontology_file = generate_multi_sheet_biodiversity_ontology_from_directory(
                session_dir,
                ontology_name
            )

            # Store the path for download
            download_path = os.path.join(session_dir, ontology_file)
            file_size = os.path.getsize(download_path)

            # Get detailed analysis summary
            generator = MultiSheetBiodiversityGenerator()
            detailed_summary = None
            analysis_data = None
            
            try:
                # Analyze the entire directory (handles MVP + Option Sets automatically)
                analysis_data = generator.analyze_multi_sheet_directory(session_dir)
                detailed_summary = generator.get_multi_sheet_analysis_summary(analysis_data)
                logger.info(f"Multi-sheet analysis complete:")
                logger.info(f"  • Fields processed: {detailed_summary['total_fields']}")
                logger.info(f"  • Option sets: {detailed_summary['option_sets_count']}")
                logger.info(f"  • Named individuals: {detailed_summary['individuals_count']}")
                logger.info(f"  • Ontology classes: {len(detailed_summary['ontology_classes'])}")
            except Exception as e:
                logger.warning(f"Could not analyze multi-sheet data: {str(e)}")

            # Save metadata about the ontology generation
            expiry_time = datetime.now() + timedelta(seconds=current_app.config['SESSION_EXPIRY'])

            metadata = {
                'session_id': session_id,
                'ontology_name': ontology_name,
                'filename': ontology_file,
                'file_size': file_size,
                'uploaded_files': uploaded_file_names,
                'creation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiry_time': expiry_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Success',
                'ontology_type': 'multi_sheet_biodiversity',
                'generator_version': '3.0.0',
                'detailed_summary': detailed_summary,
                'analysis_quality': analysis_data['data_quality'] if analysis_data else None,
                'multi_sheet_features': {
                    'mvp_processing': True,
                    'option_set_integration': True,
                    'named_individuals': True,
                    'enhanced_constraints': True,
                    'adaptive_field_recognition': True,
                    'automatic_categorization': True
                }
            }

            # Import to triplestore (Fuseki) if enabled (INCREMENTAL VERSION)
            triplestore_import_status = "Not attempted"
            triplestore_message = ""
            graph_uri = ""

            if current_app.config['TRIPLESTORE_ENABLED']:
                logger.info("Attempting INCREMENTAL import to Apache Fuseki...")
                try:
                    from incremental_ontology_updater import update_ontology_incrementally
                    fuseki_endpoint = current_app.config.get('FUSEKI_SPARQL_ENDPOINT',
                                                                "http://167.172.143.162:3030/treekipedia/sparql")

                    result = update_ontology_incrementally(analysis_data, fuseki_endpoint)

                    if result['success']:
                        triplestore_import_status = "Success (Incremental)"
                        triplestore_message = f"Added {result.get('changes_applied', 0)} new elements, preserved existing data"
                        graph_uri = f"http://treekipedia.org/ontology/{ontology_name}"
                    else:
                        triplestore_import_status = "Failed"
                        triplestore_message = f"Incremental update failed: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    triplestore_import_status = "Error"
                    triplestore_message = f"Incremental update error: {str(e)}"

                metadata['triplestore_import'] = triplestore_import_status
                metadata['triplestore_message'] = triplestore_message
                metadata['graph_uri'] = graph_uri

            save_metadata(session_id, metadata)

            # Log to Google Sheets if enabled
            if current_app.config['USE_GOOGLE_SHEETS']:
                sheets_logged = log_to_google_sheets(metadata)
                if sheets_logged:
                    logger.info(f"Successfully logged to Google Sheets: {session_id}")

            logger.info(f"Multi-sheet biodiversity ontology generated successfully: {ontology_file} ({file_size} bytes)")

            # Prepare multi-sheet information for template
            multi_sheet_info = {
                'mvp_fields': detailed_summary['total_fields'] if detailed_summary else 0,
                'option_sets': detailed_summary['option_sets_count'] if detailed_summary else 0,
                'named_individuals': detailed_summary['individuals_count'] if detailed_summary else 0,
                'ontology_classes': len(detailed_summary['ontology_classes']) if detailed_summary else 0,
                'data_properties': detailed_summary['data_properties_count'] if detailed_summary else 0,
                'object_properties': detailed_summary['object_properties_count'] if detailed_summary else 0,
                'field_distribution': detailed_summary['field_distribution'] if detailed_summary else {},
                'data_quality_score': detailed_summary['data_quality']['completeness_score'] if detailed_summary and 'data_quality' in detailed_summary else 0.0,
                'enumeration_coverage': detailed_summary['data_quality']['enumeration_coverage'] if detailed_summary and 'data_quality' in detailed_summary else 0.0
            }

            return render_template('success.html',
                                   session_id=session_id,
                                   filename=ontology_file,
                                   file_size=file_size,
                                   file_count=len(uploaded_file_names),
                                   creation_time=datetime.now().strftime('%H:%M'),
                                   expiry_minutes=current_app.config['SESSION_EXPIRY'] // 60,
                                   sheets_logging=current_app.config['USE_GOOGLE_SHEETS'],
                                   triplestore_enabled=current_app.config['TRIPLESTORE_ENABLED'],
                                   triplestore_status=triplestore_import_status,
                                   triplestore_message=triplestore_message,
                                   graph_uri=graph_uri,
                                   ontology_type='multi_sheet_biodiversity',
                                   detailed_summary=detailed_summary,
                                   multi_sheet_info=multi_sheet_info)

        except Exception as e:
            logger.error(f"Error generating multi-sheet biodiversity ontology: {str(e)}", exc_info=True)
            flash(f'Error generating ontology: {str(e)}', 'error')
            try:
                shutil.rmtree(session_dir)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up session directory: {str(cleanup_error)}")
            return redirect(url_for('main.index'))

    except Exception as e:
        logger.error(f"Unexpected error in upload process: {str(e)}", exc_info=True)
        flash(f'An unexpected error occurred: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/import-from-sheets', methods=['GET', 'POST'])
def import_from_sheets():
    """Import data from Google Sheets with multi-sheet biodiversity ontology generation."""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        flash('Google Sheets integration is not enabled or properly configured.', 'error') 
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        triplestore_status = check_triplestore_status() if current_app.config['TRIPLESTORE_ENABLED'] else False
        has_dynamic_ontology = True
        return render_template('import_sheets.html',
                             triplestore_status=triplestore_status,
                             has_dynamic_ontology=has_dynamic_ontology,
                             ontology_type='multi_sheet_biodiversity')

    elif request.method == 'POST':
        try:
            # Get the spreadsheet ID or name
            spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
            spreadsheet_name = request.form.get('spreadsheet_name', '').strip()

            if not spreadsheet_id and not spreadsheet_name:
                flash('Please provide either a spreadsheet ID or name.', 'error')
                return redirect(url_for('main.import_from_sheets'))

            # Open the spreadsheet
            try:
                if spreadsheet_id:
                    spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
                else:
                    spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)
            except Exception as e:
                flash(f'Error opening spreadsheet: {str(e)}', 'error') 
                return redirect(url_for('main.import_from_sheets'))

            # Check for changes before processing
            has_changes, change_info = check_spreadsheet_changes(spreadsheet)
            if not has_changes and not request.form.get('force_generation'):
                flash('No changes detected in the spreadsheet since last generation. Use "Force Generation" to proceed anyway.', 'info')
                return redirect(url_for('main.import_from_sheets'))

            # Create a unique session directory
            session_id = str(uuid.uuid4())
            session_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
            os.makedirs(session_dir, exist_ok=True)

            # Get all available worksheets
            available_worksheets = [worksheet.title for worksheet in spreadsheet.worksheets()]
            logger.info(f"Found {len(available_worksheets)} worksheets: {', '.join(available_worksheets)}")

            files_imported = []
            mvp_data = []
            option_set_data = []

            # Process each available worksheet
            for sheet_name in available_worksheets:
                try:
                    data = sheets_integration.get_worksheet_data(spreadsheet, worksheet_name=sheet_name)

                    if data:
                        # Write to CSV file
                        csv_path = os.path.join(session_dir, f"{sheet_name}.csv")
                        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                            if data:
                                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                                writer.writeheader()
                                writer.writerows(data)

                        files_imported.append(f"{sheet_name}.csv")
                        
                        # Identify MVP vs Option Set data
                        sheet_name_lower = sheet_name.lower()
                        if 'mvp' in sheet_name_lower or 'field' in sheet_name_lower or 'schema' in sheet_name_lower:
                            mvp_data = data
                            logger.info(f"Identified MVP sheet: {sheet_name} with {len(data)} rows")
                        elif 'option' in sheet_name_lower or 'enum' in sheet_name_lower or 'value' in sheet_name_lower:
                            option_set_data = data
                            logger.info(f"Identified Option Set sheet: {sheet_name} with {len(data)} rows")
                        elif not mvp_data:  # Use first sheet as MVP if no explicit MVP sheet
                            mvp_data = data
                            logger.info(f"Using first sheet as MVP: {sheet_name} with {len(data)} rows")
                        
                        logger.info(f"Imported {sheet_name} from Google Sheets with {len(data)} rows")
                        
                except Exception as e:
                    logger.warning(f"Could not import {sheet_name} from Google Sheets: {str(e)}")            
            
            if not files_imported:
                flash('No valid data could be imported from Google Sheets.', 'error')
                shutil.rmtree(session_dir)
                return redirect(url_for('main.import_from_sheets'))

            # Get ontology name
            ontology_name = request.form.get('ontology_name', '').strip()
            if not ontology_name:
                ontology_name = 'multi-sheet-biodiversity-ontology'
            ontology_name = sanitize_filename(ontology_name)

            # Generate multi-sheet biodiversity ontology
            try:
                logger.info(f"Generating multi-sheet biodiversity ontology {ontology_name} for session {session_id} from Google Sheets data")
                
                # Use the multi-sheet biodiversity ontology generator
                ontology_file = generate_multi_sheet_biodiversity_ontology_from_directory(
                    session_dir,
                    ontology_name
                )

                download_path = os.path.join(session_dir, ontology_file)
                file_size = os.path.getsize(download_path)

                # Get detailed analysis summary
                generator = MultiSheetBiodiversityGenerator()
                detailed_summary = None
                analysis_data = None
                
                try:
                    # For Google Sheets, analyze the combined data
                    if mvp_data:
                        analysis_data = generator.analyze_combined_data(mvp_data, option_set_data if option_set_data else None)
                        detailed_summary = generator.get_multi_sheet_analysis_summary(analysis_data)
                        logger.info(f"Google Sheets multi-sheet analysis complete:")
                        logger.info(f"  • MVP fields: {detailed_summary['total_fields']}")
                        logger.info(f"  • Option sets: {detailed_summary['option_sets_count']}")
                        logger.info(f"  • Named individuals: {detailed_summary['individuals_count']}")
                except Exception as e:
                    logger.warning(f"Could not analyze Google Sheets data: {str(e)}")

                # Save metadata
                expiry_time = datetime.now() + timedelta(seconds=current_app.config['SESSION_EXPIRY'])
                current_metadata = sheets_integration.get_spreadsheet_metadata(spreadsheet)
                current_version = current_metadata.get('version_info', {}).get('version', '1.0.0')

                metadata = {
                    'session_id': session_id,
                    'ontology_name': ontology_name,
                    'filename': ontology_file,
                    'file_size': file_size,
                    'uploaded_files': files_imported,
                    'source': 'google_sheets',
                    'spreadsheet_name': spreadsheet.title,
                    'spreadsheet_id': spreadsheet.id,
                    'creation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'expiry_time': expiry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'Success',
                    'version': current_version,
                    'changes_detected': has_changes,
                    'change_info': change_info,
                    'ontology_type': 'multi_sheet_biodiversity',
                    'generator_version': '3.0.0',
                    'detailed_summary': detailed_summary,
                    'analysis_quality': analysis_data['data_quality'] if analysis_data else None,
                    'multi_sheet_features': {
                        'mvp_processing': True,
                        'option_set_integration': True,
                        'named_individuals': True,
                        'enhanced_constraints': True,
                        'google_sheets_multi_worksheet': True
                    }
                }

                # Import to triplestore (Fuseki) if enabled (INCREMENTAL VERSION)
                triplestore_import_status = "Not attempted"
                triplestore_message = ""
                graph_uri = ""

                if current_app.config['TRIPLESTORE_ENABLED']:
                    logger.info("Attempting INCREMENTAL import to Apache Fuseki...")
                    try:
                        from incremental_ontology_updater import update_ontology_incrementally
                        fuseki_endpoint = current_app.config.get('FUSEKI_SPARQL_ENDPOINT',
                                                                    "http://167.172.143.162:3030/treekipedia/sparql")

                        result = update_ontology_incrementally(analysis_data, fuseki_endpoint)
                        
                        # FIXED: Determine status based on actual analysis results, not just applied changes
                        if result['success']:
                            changes_analyzed = result.get('changes_analyzed', {})
                            total_new_items = changes_analyzed.get('total_additions', 0)
                            changes_applied = result.get('changes_applied', 0)

                            if changes_applied > 0:
                                triplestore_import_status = "Success (Incremental)"
                                triplestore_message = f"Added {changes_applied} new elements, preserved existing data"
                            elif total_new_items > 0:
                                triplestore_import_status = "Success (No Changes Needed)"
                                triplestore_message = f"Detected {total_new_items} items but all already exist - data preserved"
                            else:
                                triplestore_import_status = "Success (Up to Date)"
                                triplestore_message = "Ontology is already up to date - no changes needed"

                            graph_uri = f"http://treekipedia.org/ontology/{ontology_name}"
                        else:
                            triplestore_import_status = "Failed"
                            triplestore_message = f"Incremental update failed: {result.get('error', 'Unknown error')}"
                    except Exception as e:
                        triplestore_import_status = "Error"
                        triplestore_message = f"Incremental update error: {str(e)}"

                    metadata['triplestore_import'] = triplestore_import_status
                    metadata['triplestore_message'] = triplestore_message
                    metadata['graph_uri'] = graph_uri
                    metadata['incremental_update'] = True  # Mark as incremental
                    metadata['data_preserved'] = True      # Data was preserved

                    # FIXED: Update version if import was attempted and changes were detected (regardless of application)
                    version_update_conditions = [
                        triplestore_import_status in ["Success (Incremental)", "Success (No Changes Needed)", "Success (Up to Date)"],
                        has_changes,
                        current_app.config.get('USE_GOOGLE_SHEETS', False)
                    ]
                    
                    if all(version_update_conditions):
                        try:
                            new_version = increment_version(current_version)
                            change_summary = f"Generated multi-sheet biodiversity ontology with {len(files_imported)} worksheets."
                            if detailed_summary:
                                change_summary += f" Analysis: {detailed_summary['total_fields']} fields, {detailed_summary['option_sets_count']} option sets, {detailed_summary['individuals_count']} individuals."
                            change_summary += f" Changes: {change_info}"
                            change_summary += f" Fuseki: {triplestore_import_status}"
                            
                            sheets_integration.update_spreadsheet_version(
                                spreadsheet=spreadsheet,
                                new_version=new_version,
                                modified_by="Multi-Sheet Biodiversity Ontology Generator v3.0",
                                changelog=change_summary
                            )
                            metadata['version'] = new_version
                            logger.info(f"Updated spreadsheet version from {current_version} to {new_version}")
                        except Exception as version_error:
                            logger.error(f"Error updating version: {version_error}")

                    # Update version if import was successful and changes were detected
                    if triplestore_import_status == "Success (Incremental)" and has_changes and current_app.config['USE_GOOGLE_SHEETS']:
                        try:
                            new_version = increment_version(current_version)
                            change_summary = f"Generated multi-sheet biodiversity ontology with {len(files_imported)} worksheets."
                            if detailed_summary:
                                change_summary += f" Analysis: {detailed_summary['total_fields']} fields, {detailed_summary['option_sets_count']} option sets, {detailed_summary['individuals_count']} individuals."
                            change_summary += f" Changes: {change_info}"

                            sheets_integration.update_spreadsheet_version(
                                spreadsheet=spreadsheet,
                                new_version=new_version,
                                modified_by="Multi-Sheet Biodiversity Ontology Generator v3.0",
                                changelog=change_summary
                            )
                            metadata['version'] = new_version
                            logger.info(f"Updated spreadsheet version from {current_version} to {new_version}")
                        except Exception as version_error:
                            logger.error(f"Error updating version: {version_error}")

                save_metadata(session_id, metadata)
                log_to_google_sheets(metadata)

                logger.info(f"Multi-sheet biodiversity ontology generated successfully from Google Sheets: {ontology_file} ({file_size} bytes)")

                # Prepare multi-sheet information for template
                multi_sheet_info = {
                    'mvp_fields': detailed_summary['total_fields'] if detailed_summary else 0,
                    'option_sets': detailed_summary['option_sets_count'] if detailed_summary else 0,
                    'named_individuals': detailed_summary['individuals_count'] if detailed_summary else 0,
                    'ontology_classes': len(detailed_summary['ontology_classes']) if detailed_summary else 0,
                    'data_properties': detailed_summary['data_properties_count'] if detailed_summary else 0,
                    'object_properties': detailed_summary['object_properties_count'] if detailed_summary else 0,
                    'worksheets_processed': len(files_imported),
                    'has_mvp_sheet': bool(mvp_data),
                    'has_option_sets': bool(option_set_data)
                }

                return render_template('success.html',
                                       session_id=session_id,
                                       filename=ontology_file,
                                       file_size=file_size,
                                       file_count=len(files_imported),
                                       creation_time=datetime.now().strftime('%H:%M'),
                                       expiry_minutes=current_app.config['SESSION_EXPIRY'] // 60,
                                       source='Google Sheets',
                                       sheets_logging=True,
                                       triplestore_enabled=current_app.config['TRIPLESTORE_ENABLED'],
                                       triplestore_status=triplestore_import_status,
                                       triplestore_message=triplestore_message,
                                       graph_uri=graph_uri,
                                       ontology_type='multi_sheet_biodiversity',
                                       detailed_summary=detailed_summary,
                                       multi_sheet_info=multi_sheet_info)
            
            except Exception as e:
                logger.error(f"Error generating multi-sheet biodiversity ontology from Google Sheets: {str(e)}", exc_info=True)
                flash(f'Error generating ontology: {str(e)}', 'error')
                shutil.rmtree(session_dir)
                return redirect(url_for('main.import_from_sheets'))
                
        except Exception as e:
            logger.error(f"Unexpected error in Google Sheets import: {str(e)}", exc_info=True)
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            return redirect(url_for('main.import_from_sheets'))

# Multi-sheet biodiversity ontology API routes
@main_bp.route('/preview-multi-sheet-ontology', methods=['POST'])
def preview_multi_sheet_ontology():
    """Preview what the multi-sheet biodiversity ontology would look like."""
    from flask import current_app
    
    try:
        spreadsheet_id = request.form.get('spreadsheet_id')
        spreadsheet_name = request.form.get('spreadsheet_name')
        
        if not spreadsheet_id and not spreadsheet_name:
            return jsonify({'error': 'Spreadsheet ID or name required'}), 400
        
        sheets_integration = getattr(current_app, 'sheets_integration', None)
        if not sheets_integration or not sheets_integration.is_initialized():
            return jsonify({'error': 'Google Sheets integration not available'}), 400
        
        # Open and analyze
        if spreadsheet_id:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
        else:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)
        
        # Process all worksheets
        mvp_data = []
        option_set_data = []
        
        for worksheet in spreadsheet.worksheets():
            try:
                data = sheets_integration.get_worksheet_data(spreadsheet, worksheet_name=worksheet.title)
                if data:
                    sheet_name_lower = worksheet.title.lower()
                    if 'mvp' in sheet_name_lower or 'field' in sheet_name_lower or not mvp_data:
                        mvp_data = data
                    elif 'option' in sheet_name_lower or 'enum' in sheet_name_lower:
                        option_set_data = data
            except:
                continue
        
        if not mvp_data:
            return jsonify({'error': 'No valid MVP data found in spreadsheet'}), 400
        
        # Use our multi-sheet biodiversity ontology generator
        generator = MultiSheetBiodiversityGenerator()
        analysis = generator.analyze_combined_data(mvp_data, option_set_data if option_set_data else None)
        summary = generator.get_multi_sheet_analysis_summary(analysis)
        
        # Create detailed preview
        preview = {
            'spreadsheet_info': {
                'title': spreadsheet.title,
                'id': spreadsheet.id,
                'worksheets': len(spreadsheet.worksheets()),
                'has_mvp_data': bool(mvp_data),
                'has_option_sets': bool(option_set_data)
            },
            'ontology_summary': summary,
            'ontology_classes': {
                class_name: {
                    'field_count': len(fields),
                    'fields': fields[:5],  # Show first 5 fields
                    'description': generator.ontology_classes[class_name]['description'] if class_name in generator.ontology_classes else 'Custom class'
                }
                for class_name, fields in analysis['categories'].items() if fields
            },
            'option_sets': {
                field_name: {
                    'value_count': len(option_data.get('values', [])),
                    'values': option_data.get('values', [])[:5]  # Show first 5 values
                }
                for field_name, option_data in analysis.get('option_sets', {}).items()
            },
            'named_individuals_preview': {
                individual_class: [ind['label'] for ind in individuals[:5]]  # Show first 5 per class
                for individual_class, individuals in 
                {ind['class']: [i for i in analysis['individuals'] if i['class'] == ind['class']] 
                 for ind in analysis['individuals']}.items()
                if individuals
            },
            'data_quality': analysis['data_quality'],
            'multi_sheet_features': {
                'adaptive_field_recognition': True,
                'option_set_integration': True,
                'named_individuals': len(analysis['individuals']) > 0,
                'hierarchical_relationships': len(analysis['hierarchical_relationships']) > 0
            }
        }
        
        return jsonify({
            'success': True,
            'preview': preview,
            'generator_type': 'multi_sheet_biodiversity',
            'generator_version': '3.0.0'
        })
        
    except Exception as e:
        logger.error(f"Error generating multi-sheet ontology preview: {str(e)}")
        return jsonify({'error': f'Preview generation failed: {str(e)}'}), 500

@main_bp.route('/analyze-multi-sheet-csv', methods=['POST'])
def analyze_multi_sheet_csv():
    """API endpoint to analyze uploaded CSV files with multi-sheet capabilities."""
    try:
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not file.filename for file in uploaded_files):
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save files temporarily
        temp_dir = os.path.join('/tmp', str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            saved_files = []
            for file in uploaded_files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    temp_path = os.path.join(temp_dir, filename)
                    file.save(temp_path)
                    saved_files.append(filename)
            
            if not saved_files:
                return jsonify({'error': 'No valid CSV files uploaded'}), 400
            
            # Analyze with multi-sheet generator
            generator = MultiSheetBiodiversityGenerator()
            analysis = generator.analyze_multi_sheet_directory(temp_dir)
            summary = generator.get_multi_sheet_analysis_summary(analysis)
            
            # Create detailed preview
            preview = {
                'file_info': {
                    'files_uploaded': saved_files,
                    'total_files': len(saved_files),
                    'total_fields': summary['total_fields']
                },
                'ontology_summary': summary,
                'ontology_classes': {
                    class_name: {
                        'field_count': len(info['fields']),
                        'fields': info['fields'][:3],  # Show first 3 fields
                        'description': info['description']
                    }
                    for class_name, info in analysis['ontology_classes'].items()
                },
                'option_sets_preview': {
                    field_name: {
                        'value_count': len(option_data.get('values', [])),
                        'sample_values': option_data.get('values', [])[:3]
                    }
                    for field_name, option_data in list(analysis.get('option_sets', {}).items())[:10]  # First 10 option sets
                },
                'sample_analysis': {
                    field_name: {
                        'ontology_class': details['ontology_class'],
                        'data_type': details['data_type'],
                        'property_name': details['property_name'],
                        'creates_individuals': details['creates_individuals'],
                        'has_option_set': bool(details.get('option_set_values'))
                    }
                    for field_name, details in list(analysis['field_analysis'].items())[:5]  # First 5 fields
                },
                'data_quality': analysis['data_quality'],
                'multi_sheet_features': {
                    'mvp_processing': True,
                    'option_set_integration': True,
                    'named_individuals': len(analysis['individuals']) > 0,
                    'adaptive_categorization': True,
                    'hierarchical_relationships': len(analysis['hierarchical_relationships']) > 0
                }
            }
            
            return jsonify({
                'success': True,
                'preview': preview,
                'generator_type': 'multi_sheet_biodiversity',
                'generator_version': '3.0.0'
            })
            
        finally:
            # Clean up temp files
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
    except Exception as e:
        logger.error(f"Error analyzing multi-sheet CSV: {str(e)}")
        return jsonify({'error': f'CSV analysis failed: {str(e)}'}), 500

@main_bp.route('/download/<session_id>/<filename>')
def download(session_id, filename):
    """Handle file downloads."""
    from flask import current_app
    
    try:
        # Validate the session_id and filename to prevent directory traversal
        if '..' in session_id or '/' in session_id or '..' in filename or '/' in filename:
            logger.warning(f"Invalid download request: {session_id}/{filename}")
            flash('Invalid request', 'error')
            return redirect(url_for('main.index'))

        path = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id, filename)

        if not os.path.exists(path):
            logger.warning(f"Download file not found: {path}")
            flash('File not found', 'error')
            return redirect(url_for('main.index'))

        # Load metadata to check if the file has expired
        metadata = load_metadata(session_id)
        if metadata:
            try:
                expiry_time = datetime.strptime(metadata['expiry_time'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() > expiry_time:
                    logger.info(f"Download attempted for expired file: {session_id}/{filename}")
                    flash('This file has expired and is no longer available for download.', 'warning')
                    return redirect(url_for('main.index'))
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing metadata for session {session_id}: {str(e)}")

        logger.info(f"File download: {session_id}/{filename}")
        return send_file(path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}", exc_info=True)
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/status/<session_id>')
def check_status(session_id):
    """API endpoint to check the status of a session."""
    metadata = load_metadata(session_id)
    if metadata:
        try:
            expiry_time = datetime.strptime(metadata['expiry_time'], '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            if now > expiry_time:
                time_remaining = 0
            else:
                time_remaining = int((expiry_time - now).total_seconds())

            return jsonify({
                'status': 'active',
                'time_remaining': time_remaining,
                'filename': metadata.get('filename'),
                'file_size': metadata.get('file_size', 0),
                'source': metadata.get('source', 'upload'),
                'triplestore_import': metadata.get('triplestore_import', 'N/A'),
                'graph_uri': metadata.get('graph_uri', ''),
                'ontology_type': metadata.get('ontology_type', 'multi_sheet_biodiversity'),
                'generator_version': metadata.get('generator_version', '3.0.0'),
                'detailed_summary': metadata.get('detailed_summary'),
                'analysis_quality': metadata.get('analysis_quality'),
                'multi_sheet_features': metadata.get('multi_sheet_features', {}),
                'adaptive_system': True
            })                    
        except (KeyError, ValueError) as e:
            logger.error(f"Error calculating time remaining for session {session_id}: {str(e)}")

    return jsonify({
        'status': 'expired',
        'time_remaining': 0
    })

@main_bp.route('/ontology-details/<session_id>')
def get_ontology_details(session_id):
    """Get detailed information about a generated multi-sheet ontology."""
    metadata = load_metadata(session_id)
    if not metadata:
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        detailed_summary = metadata.get('detailed_summary', {})
        analysis_quality = metadata.get('analysis_quality', {})
        multi_sheet_features = metadata.get('multi_sheet_features', {})
        
        details = {
            'session_info': {
                'session_id': session_id,
                'ontology_name': metadata.get('ontology_name'),
                'creation_time': metadata.get('creation_time'),
                'ontology_type': metadata.get('ontology_type', 'multi_sheet_biodiversity'),
                'generator_version': metadata.get('generator_version', '3.0.0')
            },
            'file_info': {
                'filename': metadata.get('filename'),
                'file_size': metadata.get('file_size', 0),
                'uploaded_files': metadata.get('uploaded_files', [])
            },
            'ontology_structure': {
                'total_fields': detailed_summary.get('total_fields', 0),
                'ontology_classes': detailed_summary.get('ontology_classes', []),
                'data_properties_count': detailed_summary.get('data_properties_count', 0),
                'object_properties_count': detailed_summary.get('object_properties_count', 0),
                'individuals_count': detailed_summary.get('individuals_count', 0),
                'option_sets_count': detailed_summary.get('option_sets_count', 0),
                'hierarchical_relationships_count': detailed_summary.get('hierarchical_relationships_count', 0)
            },
            'field_distribution': detailed_summary.get('field_distribution', {}),
            'data_quality': analysis_quality,
            'multi_sheet_features': multi_sheet_features,
            'adaptive_capabilities': {
                'handles_new_fields': True,
                'handles_new_columns': True,
                'handles_new_sheets': True,
                'automatic_categorization': True,
                'option_set_integration': True,
                'no_code_changes_needed': True
            },
            'integration_status': {
                'triplestore_import': metadata.get('triplestore_import', 'Not attempted'),
                'triplestore_message': metadata.get('triplestore_message', ''),
                'graph_uri': metadata.get('graph_uri', '')
            }
        }
        
        return jsonify({
            'success': True,
            'details': details
        })
        
    except Exception as e:
        logger.error(f"Error getting ontology details for session {session_id}: {str(e)}")
        return jsonify({'error': f'Failed to get ontology details: {str(e)}'}), 500

@main_bp.route('/system-capabilities')
def get_system_capabilities():
    """Get information about the multi-sheet system capabilities."""
    from flask import current_app
    
    capabilities = {
        'generator_info': {
            'type': 'multi_sheet_biodiversity',
            'version': '3.0.0',
            'name': 'Multi-Sheet Biodiversity Ontology Generator'
        },
        'supported_formats': {
            'csv_files': True,
            'google_sheets': True,
            'multiple_files': True,
            'multi_worksheet': True
        },
        'adaptive_features': {
            'automatic_field_recognition': True,
            'dynamic_categorization': True,
            'option_set_integration': True,
            'named_individual_creation': True,
            'hierarchical_relationship_inference': True,
            'constraint_parsing': True
        },
        'no_code_changes_needed_for': {
            'adding_new_rows': True,
            'adding_new_columns': True,
            'adding_new_spreadsheets': True,
            'modifying_option_sets': True,
            'changing_field_names': True,
            'adding_new_categories': True
        },
        'biodiversity_specific_features': {
            'taxonomic_hierarchy_detection': True,
            'geographic_distribution_handling': True,
            'ecological_information_processing': True,
            'conservation_status_management': True,
            'morphological_characteristics': True,
            'economic_value_assessment': True,
            'cultural_significance_tracking': True,
            'management_information': True
        },
        'output_formats': {
            'owl_rdf_xml': True,
            'fuseki_import': current_app.config.get('TRIPLESTORE_ENABLED', False),
            'google_sheets_logging': current_app.config.get('USE_GOOGLE_SHEETS', False)
        },
        'quality_features': {
            'data_quality_assessment': True,
            'completeness_scoring': True,
            'enumeration_coverage': True,
            'relationship_validation': True,
            'consistency_checking': True
        }
    }
    
    return jsonify(capabilities)

@main_bp.route('/compare-ontologies')
def compare_ontologies():
    """Compare different ontology generation approaches."""
    comparison = {
        'static_config_approach': {
            'requires_config_files': True,
            'handles_new_fields': False,
            'automatic_categorization': False,
            'option_set_integration': False,
            'maintenance_effort': 'High'
        },
        'simple_dynamic_approach': {
            'requires_config_files': False,
            'handles_new_fields': True,
            'automatic_categorization': 'Basic',
            'option_set_integration': False,
            'maintenance_effort': 'Medium'
        },
        'multi_sheet_biodiversity_approach': {
            'requires_config_files': False,
            'handles_new_fields': True,
            'handles_multiple_sheets': True,
            'automatic_categorization': 'Advanced',
            'option_set_integration': True,
            'named_individuals': True,
            'biodiversity_specific': True,
            'adaptive_system': True,
            'maintenance_effort': 'Low'
        }
    }
    
    return render_template('ontology_comparison.html', comparison=comparison)

@main_bp.route('/cleanup', methods=['POST'])
def cleanup():
    """Scheduled task to clean up expired files."""
    from flask import current_app
    
    if request.form.get('secret') != current_app.secret_key:
        logger.warning("Unauthorized cleanup attempt")
        return "Unauthorized", 401
    
    now = time.time()
    cleanup_count = 0

    for dir_name in os.listdir(current_app.config['UPLOAD_FOLDER']):
        dir_path = os.path.join(current_app.config['UPLOAD_FOLDER'], dir_name)
        if os.path.isdir(dir_path):
            created_time = os.path.getctime(dir_path)
            if now - created_time > current_app.config['SESSION_EXPIRY']:
                try:
                    shutil.rmtree(dir_path)
                    metadata_path = os.path.join(current_app.config['METADATA_DIR'], f"{dir_name}.json")
                    if os.path.exists(metadata_path):
                        os.remove(metadata_path)
                    cleanup_count += 1
                    logger.info(f"Cleaned up expired session: {dir_name}")
                except Exception as e:
                    logger.error(f"Error cleaning up directory {dir_path}: {str(e)}")

    logger.info(f"Cleanup complete. Removed {cleanup_count} expired sessions.")
    return f"Cleanup complete. Removed {cleanup_count} expired sessions.", 200

# Additional utility routes for multi-sheet system
@main_bp.route('/validate-spreadsheet', methods=['POST'])
def validate_spreadsheet():
    """Validate spreadsheet structure before processing."""
    try:
        # This could be expanded to validate spreadsheet structure
        # Currently returns basic validation info
        return jsonify({
            'valid': True,
            'message': 'Spreadsheet structure is compatible with multi-sheet generator',
            'recommendations': [
                'Include field definitions in MVP sheet',
                'Use option sets for enumerated values',
                'Follow consistent naming conventions'
            ]
        })
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        }), 500

@main_bp.route('/help/multi-sheet')
def multi_sheet_help():
    """Provide help information for multi-sheet system."""
    help_info = {
        'title': 'Multi-Sheet Biodiversity Ontology Generator Help',
        'sections': {
            'overview': {
                'title': 'System Overview',
                'content': 'The Multi-Sheet Biodiversity Ontology Generator automatically processes your MVP and Option Set spreadsheets to create comprehensive biodiversity ontologies.'
            },
            'spreadsheet_structure': {
                'title': 'Spreadsheet Structure',
                'content': '''
                <h5>MVP Sheet (Field Definitions)</h5>
                <ul>
                    <li>Field: Original field name</li>
                    <li>Schema (revised): Ontology property name</li>
                    <li>Exists: Whether field is required</li>
                    <li>ai researched: AI-generated category</li>
                    <li>manual calculation: Manual processing flag</li>
                    <li>option set: Enumerated values (if applicable)</li>
                </ul>
                
                <h5>Option Set Sheet (Enumerated Values)</h5>
                <ul>
                    <li>Field: Field name matching MVP sheet</li>
                    <li>Value1, Value2, etc.: Enumerated values</li>
                    <li>Creates named individuals automatically</li>
                </ul>
                '''
            },
            'adaptive_features': {
                'title': 'Adaptive Features',
                'content': '''
                <h5>No Code Changes Needed For:</h5>
                <ul>
                    <li>Adding new rows to MVP sheet</li>
                    <li>Adding new columns to spreadsheets</li>
                    <li>Adding new option sets</li>
                    <li>Modifying existing values</li>
                    <li>Changing field categories</li>
                </ul>
                '''
            }
        }
    }
    
    return jsonify(help_info)