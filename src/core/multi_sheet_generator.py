import csv
import os
import json
from owlready2 import *
import logging
from typing import Dict, List, Any, Optional, Tuple
import re
import hashlib
import datetime
import html
import unicodedata

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Owlready2 to store the ontology in memory
onto_path.append(".")
ONTOLOGY_IRI = "http://www.example.org/biodiversity-ontology"

def sanitize_xml_name(name: str) -> str:
    """
    Sanitize a string to be XML-safe for use in ontology names/IRIs.
    """
    if not name:
        return "EmptyValue"
    
    # Convert to string and strip whitespace
    clean_name = str(name).strip()
    
    # Remove or replace problematic characters
    replacements = {
        '<': 'LessThan', '>': 'GreaterThan', '&': 'And', '"': 'Quote', "'": 'Apostrophe',
        '/': '_', '\\': '_', ':': '_', ';': '_', '|': '_', '?': '_', '*': '_',
        '+': 'Plus', '=': 'Equals', '%': 'Percent', '#': '_', '@': 'At',
        '!': '_', '$': '_', '^': '_', '~': '_', '`': '_',
        '[': '_', ']': '_', '{': '_', '}': '_', '(': '_', ')': '_',
        '\n': '_', '\r': '_', '\t': '_'
    }
    
    # Apply replacements
    for char, replacement in replacements.items():
        clean_name = clean_name.replace(char, replacement)
    
    # Remove any remaining non-ASCII characters and normalize
    clean_name = unicodedata.normalize('NFKD', clean_name)
    clean_name = ''.join(c for c in clean_name if c.isascii())
    
    # Replace spaces and multiple underscores
    clean_name = re.sub(r'\s+', '_', clean_name)
    clean_name = re.sub(r'_{2,}', '_', clean_name)
    
    # Remove leading/trailing underscores
    clean_name = clean_name.strip('_')
    
    # Ensure it starts with a letter (XML requirement)
    if clean_name and not clean_name[0].isalpha():
        clean_name = 'Item_' + clean_name
    
    # Ensure it's not empty
    if not clean_name:
        clean_name = "UnknownValue"
    
    # Limit length to prevent overly long IRIs
    if len(clean_name) > 100:
        clean_name = clean_name[:100]
    
    return clean_name

def sanitize_xml_content(content: str) -> str:
    """
    Sanitize content for XML attributes and text content.
    """
    if not content:
        return ""
    
    # Escape XML entities
    content = html.escape(str(content))
    
    # Remove control characters that aren't allowed in XML
    content = ''.join(char for char in content if ord(char) >= 32 or char in '\t\n\r')
    
    return content

class MultiSheetBiodiversityGenerator:
    """
    Enhanced biodiversity ontology generator that handles multiple sheets:
    1. MVP sheet with field definitions
    2. Option Set sheet with enumerated values
    """
    
    def __init__(self):
        # Enhanced field detection patterns for biodiversity data
        self.field_patterns = {
            # Taxonomic fields
            'TAXON_ID': re.compile(r'(taxon_id|species_id|tax_id|id)', re.IGNORECASE),
            'SCIENTIFIC_NAME': re.compile(r'(scientific_name|species|binomial|taxon_name)', re.IGNORECASE),
            'COMMON_NAME': re.compile(r'(common_name|vernacular|local_name)', re.IGNORECASE),
            'FAMILY': re.compile(r'(family|taxonomic_family)', re.IGNORECASE),
            'GENUS': re.compile(r'(genus|taxonomic_genus)', re.IGNORECASE),
            'ORDER': re.compile(r'(order|taxonomic_order)', re.IGNORECASE),
            'CLASS': re.compile(r'(class|taxonomic_class)', re.IGNORECASE),
            'KINGDOM': re.compile(r'(kingdom|taxonomic_kingdom)', re.IGNORECASE),
            
            # Geographic fields
            'COUNTRIES_NATIVE': re.compile(r'(countries_native|native_countries|origin_countries)', re.IGNORECASE),
            'COUNTRIES_INTRODUCED': re.compile(r'(countries_introduced|introduced_countries|non_native)', re.IGNORECASE),
            'COUNTRIES_INVASIVE': re.compile(r'(countries_invasive|invasive_countries)', re.IGNORECASE),
            'DISTRIBUTION': re.compile(r'(distribution|range|geographic_range)', re.IGNORECASE),
            'BIOREGIONS': re.compile(r'(bioregions|bioregion|ecoregions)', re.IGNORECASE),
            
            # Ecological fields
            'BIOMES': re.compile(r'(biomes|biome|ecosystem)', re.IGNORECASE),
            'HABITAT': re.compile(r'(habitat|habitat_type|primary_habitat)', re.IGNORECASE),
            'ELEVATION': re.compile(r'(elevation|altitude|height_range)', re.IGNORECASE),
            'ECOLOGICAL_FUNCTION': re.compile(r'(ecological_function|ecosystem_role)', re.IGNORECASE),
            
            # Conservation fields
            'CONSERVATION_STATUS': re.compile(r'(conservation_status|iucn_status|threat_status)', re.IGNORECASE),
            'THREATS': re.compile(r'(threats|threatening_processes)', re.IGNORECASE),
            'CLIMATE_VULNERABILITY': re.compile(r'(climate.*vulnerability|climate.*change)', re.IGNORECASE),
            
            # Morphological fields
            'HEIGHT': re.compile(r'(height|maximum_height|max_height)', re.IGNORECASE),
            'DIAMETER': re.compile(r'(diameter|maximum_diameter|dbh)', re.IGNORECASE),
            'GROWTH_FORM': re.compile(r'(growth_form|form|habit)', re.IGNORECASE),
            'LEAF_TYPE': re.compile(r'(leaf_type|leaf_form|foliage)', re.IGNORECASE),
            
            # Economic fields
            'TIMBER_VALUE': re.compile(r'(timber|wood|commercial_value)', re.IGNORECASE),
            'NON_TIMBER': re.compile(r'(non_timber|ntfp|non_wood)', re.IGNORECASE),
            'AGROFORESTRY': re.compile(r'(agroforestry|farming)', re.IGNORECASE),
            
            # Cultural fields
            'CULTURAL_SIGNIFICANCE': re.compile(r'(cultural|traditional|indigenous)', re.IGNORECASE),
            'TRADITIONAL_USES': re.compile(r'(traditional_uses|ethnobotanical)', re.IGNORECASE),
            
            # Management fields
            'STEWARDSHIP': re.compile(r'(stewardship|management|best_practices)', re.IGNORECASE),
            'PLANTING': re.compile(r'(planting|cultivation|propagation)', re.IGNORECASE),
            'MAINTENANCE': re.compile(r'(maintenance|care|pruning)', re.IGNORECASE)
        }
        
        # Biodiversity-specific ontology classes with detailed properties
        self.ontology_classes = {
            'TaxonomicRank': {
                'properties': ['taxonId', 'scientificName', 'commonName', 'family', 'genus', 'order', 'class', 'kingdom'],
                'description': 'Taxonomic classification information'
            },
            'GeographicDistribution': {
                'properties': ['countriesNative', 'countriesIntroduced', 'countriesInvasive', 'bioregions', 'distribution'],
                'description': 'Geographic distribution and origin information'
            },
            'EcologicalInformation': {
                'properties': ['biomes', 'habitat', 'elevationMin', 'elevationMax', 'ecologicalFunction'],
                'description': 'Ecological characteristics and habitat requirements'
            },
            'ConservationInformation': {
                'properties': ['conservationStatus', 'threats', 'climateVulnerability'],
                'description': 'Conservation status and threat information'
            },
            'MorphologicalCharacteristics': {
                'properties': ['maximumHeight', 'maximumDiameter', 'growthForm', 'leafType'],
                'description': 'Physical and morphological characteristics'
            },
            'EconomicValue': {
                'properties': ['timberValue', 'nonTimberProducts', 'agroforestryUses'],
                'description': 'Economic importance and commercial uses'
            },
            'CulturalSignificance': {
                'properties': ['culturalSignificance', 'traditionalUses'],
                'description': 'Cultural and traditional significance'
            },
            'ManagementInformation': {
                'properties': ['stewardshipPractices', 'plantingRecommendations', 'maintenanceRequirements'],
                'description': 'Management and stewardship information'
            }
        }

    def analyze_multi_sheet_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        Analyze directory containing multiple CSV files (MVP + Option Sets).
        """
        logger.info(f"Analyzing multi-sheet directory: {directory_path}")
        
        # Find CSV files
        csv_files = [f for f in os.listdir(directory_path) if f.endswith('.csv')]
        logger.info(f"Found CSV files: {csv_files}")
        
        # Identify MVP and Option Set files
        mvp_file = None
        option_set_file = None
        
        for file in csv_files:
            file_lower = file.lower()
            # Check for MVP/field definition files (including species as it contains field definitions)
            if 'mvp' in file_lower or 'field' in file_lower or 'schema' in file_lower or 'species' in file_lower:
                mvp_file = os.path.join(directory_path, file)
                logger.info(f"Identified MVP file: {file}")
            # Check for option set files
            elif 'option' in file_lower or 'enum' in file_lower or 'value' in file_lower:
                option_set_file = os.path.join(directory_path, file)
                logger.info(f"Identified Option Set file: {file}")
            # Skip metadata sheets (they contain version info, not field definitions)
            elif 'metadata' in file_lower:
                logger.info(f"Skipping metadata sheet: {file} (used for version tracking)")
        
        # If not found by name, use first file as MVP
        if not mvp_file and csv_files:
            mvp_file = os.path.join(directory_path, csv_files[0])
            logger.info(f"Using first file as MVP: {csv_files[0]}")
        
        # If second file exists, use as option set
        if not option_set_file and len(csv_files) > 1:
            option_set_file = os.path.join(directory_path, csv_files[1])
            logger.info(f"Using second file as Option Set: {csv_files[1]}")
        
        # Check if this is a schema definition file or actual data file
        # by looking at the column names in the first CSV file
        if mvp_file and os.path.exists(mvp_file):
            with open(mvp_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                first_row = next(reader, None)
                if first_row:
                    columns = list(first_row.keys())
                    # If columns are actual field names (not 'Field', 'Schema', etc.),
                    # treat them as direct schema
                    if 'Field' not in columns and 'Schema' not in ' '.join(columns):
                        logger.info("Detected direct schema format (columns are field names)")
                        return self.analyze_direct_schema(mvp_file, option_set_file)

        return self.analyze_mvp_and_option_sets(mvp_file, option_set_file)

    def analyze_direct_schema(self, schema_file: str, option_set_file: str = None) -> Dict[str, Any]:
        """
        Analyze a schema file where column names ARE the field definitions.
        This handles the case where species sheet has columns like:
        species_scientific_name, family, genus, etc.

        Also handles transposed format where field names are in rows instead of columns.
        """
        logger.info("Analyzing direct schema format...")

        # Read the schema file to get column names
        field_names = []
        if schema_file and os.path.exists(schema_file):
            with open(schema_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                field_names = reader.fieldnames or []

                # Check if this is a transposed format (many rows, 1 column)
                # Read all rows to see if field names are stored vertically
                rows = list(reader)

                # If we have only 1 column but many rows, it's transposed
                if len(field_names) == 1 and len(rows) > 10:
                    logger.info(f"Detected transposed format: {len(rows)} field names in single column")
                    # Get field names from the first column of all rows
                    column_name = field_names[0]
                    field_names = [row[column_name].strip() for row in rows if row.get(column_name, '').strip()]
                    # Filter out empty values
                    field_names = [f for f in field_names if f]
                    logger.info(f"Extracted {len(field_names)} field names from transposed format")

            logger.info(f"Found {len(field_names)} fields in schema: {field_names[:10]}...")

        # Read option sets
        option_set_data = []
        option_sets = {}
        if option_set_file and os.path.exists(option_set_file):
            logger.info(f"Reading Option Set file: {option_set_file}")
            with open(option_set_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                option_set_data = list(reader)

            # Process option sets - each column is an option set
            option_sets = self._process_option_sets(option_set_data)
            logger.info(f"Found {len(option_sets)} option sets")

        # Build analysis structure
        analysis = {
            'version': hashlib.md5(''.join(field_names).encode()).hexdigest()[:8],
            'timestamp': datetime.datetime.now().isoformat(),
            'field_analysis': {},
            'ontology_classes': {},
            'object_properties': [],
            'data_properties': [],
            'individuals': [],
            'hierarchical_relationships': [],
            'categories': {},
            'data_quality': {},
            'option_sets': option_sets
        }

        # Track fields by category
        categorized_fields = {class_name: [] for class_name in self.ontology_classes.keys()}

        # Analyze each field (column name)
        for field_name in field_names:
            if not field_name or field_name.strip() == '':
                continue

            # Infer category and type from field name
            category = self._determine_ontology_class(field_name)
            data_type = self._infer_data_type_from_name(field_name)
            property_name = self._generate_property_name(field_name)

            # Check if field has option set
            has_option_set = field_name in option_sets
            constraints = []
            if has_option_set:
                constraints.append(f"enum: {', '.join(option_sets[field_name]['values'][:5])}")

            # Infer range class for fields with option sets
            range_class = None
            if has_option_set:
                range_class = self._infer_class_from_field(field_name)

            field_info = {
                'original_field': field_name,
                'schema_field': field_name,
                'category': category,
                'ontology_class': category,  # Add for compatibility with quality assessment
                'data_type': data_type,
                'property_name': property_name,
                'constraints': constraints,
                'has_option_set': has_option_set,
                'option_set_name': field_name if has_option_set else None,
                'option_set_values': option_sets.get(field_name, {}).get('values', []) if has_option_set else None,
                'range_class': range_class,  # Add for individual generation
                'description': f"Biodiversity field: {field_name}",
                'is_required': False,
                'required': False  # Add for compatibility with quality assessment
            }

            analysis['field_analysis'][field_name] = field_info

            # Categorize field
            categorized_fields[category].append(field_name)

            # Add to ontology class
            if category not in analysis['ontology_classes']:
                analysis['ontology_classes'][category] = {
                    'fields': [],
                    'description': f'{category} related fields'
                }
            analysis['ontology_classes'][category]['fields'].append(field_name)

            # Create property
            if data_type in ['string', 'int', 'float', 'date', 'boolean']:
                analysis['data_properties'].append({
                    'name': property_name,
                    'domain': category,
                    'range': data_type,
                    'description': field_info['description']
                })
            else:
                analysis['object_properties'].append({
                    'name': property_name,
                    'domain': category,
                    'range': data_type,
                    'description': field_info['description']
                })

        # Generate individuals from option sets
        analysis['individuals'] = self._generate_individuals_from_option_sets(
            analysis['field_analysis'], option_sets
        )

        # Calculate data quality
        analysis['data_quality'] = self._assess_data_quality_with_option_sets(
            analysis['field_analysis'], option_sets
        )

        analysis['categories'] = categorized_fields

        logger.info(f"Direct schema analysis complete: {len(analysis['field_analysis'])} fields")
        return analysis

    def _infer_data_type_from_name(self, field_name: str) -> str:
        """Infer data type from field name."""
        name_lower = field_name.lower()

        if any(x in name_lower for x in ['id', 'code', 'key']):
            return 'string'
        elif any(x in name_lower for x in ['count', 'number', 'total', 'occurrences']):
            return 'int'
        elif any(x in name_lower for x in ['elevation', 'temperature', 'altitude', 'height']):
            return 'float'
        elif any(x in name_lower for x in ['date', 'year', 'time']):
            return 'date'
        elif any(x in name_lower for x in ['is_', 'has_', 'can_']):
            return 'boolean'
        else:
            return 'string'

    def analyze_mvp_and_option_sets(self, mvp_file: str, option_set_file: str = None) -> Dict[str, Any]:
        """
        Analyze MVP file and optional Option Set file.
        """
        logger.info("Starting multi-sheet biodiversity ontology analysis...")
        
        # Read MVP file
        mvp_data = []
        if mvp_file and os.path.exists(mvp_file):
            logger.info(f"Reading MVP file: {mvp_file}")
            try:
                with open(mvp_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    mvp_data = list(reader)
                logger.info(f"MVP file: {len(mvp_data)} rows, columns: {list(mvp_data[0].keys()) if mvp_data else 'None'}")
            except Exception as e:
                logger.error(f"Error reading MVP file: {str(e)}")
        
        # Read Option Set file
        option_set_data = []
        if option_set_file and os.path.exists(option_set_file):
            logger.info(f"Reading Option Set file: {option_set_file}")
            try:
                with open(option_set_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    option_set_data = list(reader)
                logger.info(f"Option Set file: {len(option_set_data)} rows, columns: {list(option_set_data[0].keys()) if option_set_data else 'None'}")
            except Exception as e:
                logger.error(f"Error reading Option Set file: {str(e)}")
        
        return self.analyze_combined_data(mvp_data, option_set_data)

    def analyze_combined_data(self, mvp_data: List[Dict[str, Any]], option_set_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze combined MVP and Option Set data.
        """
        analysis = {
            'version': self._generate_version_hash(mvp_data + (option_set_data or [])),
            'timestamp': datetime.datetime.now().isoformat(),
            'field_analysis': {},
            'ontology_classes': {},
            'object_properties': [],
            'data_properties': [],
            'individuals': [],
            'hierarchical_relationships': [],
            'categories': {},
            'data_quality': {},
            'option_sets': {}
        }
        
        # First, process option sets to build enumeration mappings
        if option_set_data:
            logger.info("Processing option sets...")
            analysis['option_sets'] = self._process_option_sets(option_set_data)
            logger.info(f"Found {len(analysis['option_sets'])} option sets")
        
        # Track fields by category
        categorized_fields = {class_name: [] for class_name in self.ontology_classes.keys()}
        
        # Process MVP data
        logger.info(f"Processing MVP data: {len(mvp_data)} rows")
        processed_count = 0
        skipped_count = 0
        
        for i, row in enumerate(mvp_data):
            # Extract data with flexible column matching
            field = ''
            schema_field = ''
            exists = ''
            manual_calc = ''
            option_set = ''
            ai_category = ''
            
            # Flexible column matching
            for key, value in row.items():
                key_clean = key.strip().lower()
                value_str = str(value).strip() if value else ''
                
                if key_clean == 'field':
                    field = value_str
                elif 'schema' in key_clean and 'revised' in key_clean:
                    schema_field = value_str
                elif key_clean == 'exists':
                    exists = value_str
                elif 'manual' in key_clean and 'calc' in key_clean:
                    manual_calc = value_str
                elif 'option' in key_clean and 'set' in key_clean:
                    option_set = value_str
                elif 'ai' in key_clean and 'research' in key_clean:
                    ai_category = value_str
            
            # Debug first few rows
            if i < 5:
                logger.info(f"Row {i+1}: field='{field}', schema='{schema_field}', option_set='{option_set}'")
            
            # Skip empty rows
            if not field or not schema_field:
                if i < 10:
                    logger.warning(f"Row {i+1}: Skipping - field='{field}', schema='{schema_field}'")
                skipped_count += 1
                continue
            
            try:
                # Enhanced field analysis with option set integration
                field_info = self._analyze_biodiversity_field_with_options(
                    field, schema_field, ai_category, manual_calc, option_set, exists, analysis['option_sets']
                )
                
                analysis['field_analysis'][schema_field] = field_info
                
                # Categorize field
                category = field_info['ontology_class']
                if category in categorized_fields:
                    categorized_fields[category].append(schema_field)
                
                processed_count += 1
                
                if i < 10:
                    logger.info(f"Row {i+1}: ✅ '{field}' -> '{schema_field}' (category: {category})")
                
            except Exception as e:
                logger.error(f"Row {i+1}: ❌ Error processing '{field}': {str(e)}")
                skipped_count += 1
        
        logger.info(f"MVP processing complete: {processed_count} processed, {skipped_count} skipped")
        
        # Create ontology structure
        for class_name, fields in categorized_fields.items():
            if fields:
                analysis['ontology_classes'][class_name] = {
                    'fields': fields,
                    'description': self.ontology_classes[class_name]['description']
                }
                logger.info(f"Created class {class_name} with {len(fields)} fields")
        
        # Generate properties and relationships
        if analysis['field_analysis']:
            analysis['data_properties'] = self._generate_data_properties(analysis['field_analysis'])
            analysis['object_properties'] = self._generate_object_properties_with_option_sets(analysis['field_analysis'], analysis['option_sets'])
            analysis['hierarchical_relationships'] = self._generate_hierarchical_relationships(analysis['field_analysis'])
            analysis['individuals'] = self._generate_individuals_from_option_sets(analysis['field_analysis'], analysis['option_sets'])
            logger.info(f"Generated {len(analysis['data_properties'])} data properties, {len(analysis['object_properties'])} object properties, {len(analysis['individuals'])} individuals")
        else:
            logger.warning("No fields processed - using defaults")
            analysis['data_properties'] = []
            analysis['object_properties'] = self._get_default_object_properties()
            analysis['hierarchical_relationships'] = []
            analysis['individuals'] = []
        
        # Categories for compatibility
        analysis['categories'] = {class_name: info['fields'] for class_name, info in analysis['ontology_classes'].items()}
        
        # Enhanced data quality assessment
        analysis['data_quality'] = self._assess_data_quality_with_option_sets(analysis['field_analysis'], analysis['option_sets'])
        
        logger.info(f"✅ Multi-sheet analysis complete: {len(analysis['field_analysis'])} fields, {len(analysis['ontology_classes'])} classes, {len(analysis['individuals'])} individuals")
        
        return analysis

    def _process_option_sets(self, option_set_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Process option set data to create enumeration mappings.
        """
        option_sets = {}
        
        for row in option_set_data:
            # Each column represents a different option set
            for key, value in row.items():
                key_clean = key.strip()
                value_str = str(value).strip() if value else ''
                
                if not value_str or value_str.lower() in ['', 'nan', 'none', 'null']:
                    continue
                
                # Initialize option set if not exists
                if key_clean not in option_sets:
                    option_sets[key_clean] = {
                        'values': [],
                        'type': 'enumeration',
                        'count': 0
                    }
                
                # Add unique values
                if value_str not in option_sets[key_clean]['values']:
                    option_sets[key_clean]['values'].append(value_str)
                    option_sets[key_clean]['count'] += 1
        
        return option_sets

    def _analyze_biodiversity_field_with_options(self, field: str, schema_field: str, ai_category: str, 
                                               manual_calc: str, option_set: str, exists: str, 
                                               option_sets: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced field analysis that incorporates option set data.
        """
        combined_text = f"{field} {schema_field} {ai_category}".lower()
        
        # Determine ontology class
        ontology_class = self._determine_ontology_class(combined_text)
        data_type = self._infer_data_type(combined_text, option_set)
        property_name = self._generate_property_name(schema_field)
        
        # Enhanced constraint parsing with option sets
        constraints = self._parse_enhanced_constraints(option_set, data_type)
        
        # Check if this field has option sets defined
        option_set_values = None
        if schema_field in option_sets:
            option_set_values = option_sets[schema_field]['values']
            constraints['enumeration'] = option_set_values
            constraints['type'] = 'enumeration'
        elif field in option_sets:
            option_set_values = option_sets[field]['values']
            constraints['enumeration'] = option_set_values
            constraints['type'] = 'enumeration'
        
        # Determine if this creates individuals
        creates_individuals = self._creates_individuals(combined_text, option_set) or bool(option_set_values)
        
        return {
            'original_field': field,
            'schema_field': schema_field,
            'property_name': property_name,
            'ontology_class': ontology_class,
            'data_type': data_type if not option_set_values else 'enumeration',
            'ai_category': ai_category,
            'required': self._is_required_field(exists, field),
            'source_type': self._determine_source_type(ai_category, manual_calc),
            'constraints': constraints,
            'creates_individuals': creates_individuals,
            'range_class': self._determine_range_class(combined_text, data_type),
            'is_hierarchical': self._is_hierarchical_field(combined_text),
            'option_set_values': option_set_values
        }

    def _generate_individuals_from_option_sets(self, field_analysis: Dict[str, Any], option_sets: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate named individuals from option sets and field constraints.
        """
        individuals = []
        
        for field_name, field_info in field_analysis.items():
            if field_info.get('option_set_values'):
                range_class = field_info['range_class'] or self._infer_class_from_field(field_name)
                
                for value in field_info['option_set_values']:
                    individual = {
                        'name': sanitize_xml_name(value),
                        'class': range_class,
                        'label': sanitize_xml_content(value),
                        'original_value': value,
                        'source_field': field_name,
                        'source': 'option_set'
                    }
                    individuals.append(individual)
        
        # Also process direct option sets
        for field_name, option_data in option_sets.items():
            if 'values' in option_data:
                range_class = self._infer_class_from_field(field_name)
                
                for value in option_data['values']:
                    individual = {
                        'name': sanitize_xml_name(value),
                        'class': range_class,
                        'label': sanitize_xml_content(value),
                        'original_value': value,
                        'source_field': field_name,
                        'source': 'direct_option_set'
                    }
                    individuals.append(individual)
        
        # Remove duplicates
        seen = set()
        unique_individuals = []
        for ind in individuals:
            key = (ind['name'], ind['class'])
            if key not in seen:
                seen.add(key)
                unique_individuals.append(ind)
        
        return unique_individuals

    def _infer_class_from_field(self, field_name: str) -> str:
        """
        Infer the appropriate class for individuals based on field name.
        """
        field_lower = field_name.lower()
        
        if 'country' in field_lower or 'countries' in field_lower:
            return 'Country'
        elif 'biome' in field_lower:
            return 'Biome'
        elif 'habitat' in field_lower:
            return 'Habitat'
        elif 'conservation' in field_lower or 'status' in field_lower:
            return 'ConservationStatus'
        elif 'threat' in field_lower:
            return 'Threat'
        elif 'growth' in field_lower and 'form' in field_lower:
            return 'GrowthForm'
        elif 'value' in field_lower or 'timber' in field_lower:
            return 'EconomicValue'
        else:
            return 'EnumeratedValue'

    # Helper methods
    def _determine_ontology_class(self, text: str) -> str:
        """Determine which ontology class this field belongs to."""
        for pattern_name, pattern in self.field_patterns.items():
            if pattern.search(text):
                if pattern_name in ['TAXON_ID', 'SCIENTIFIC_NAME', 'COMMON_NAME', 'FAMILY', 'GENUS', 'ORDER', 'CLASS', 'KINGDOM']:
                    return 'TaxonomicRank'
                elif pattern_name in ['COUNTRIES_NATIVE', 'COUNTRIES_INTRODUCED', 'COUNTRIES_INVASIVE', 'DISTRIBUTION', 'BIOREGIONS']:
                    return 'GeographicDistribution'
                elif pattern_name in ['BIOMES', 'HABITAT', 'ELEVATION', 'ECOLOGICAL_FUNCTION']:
                    return 'EcologicalInformation'
                elif pattern_name in ['CONSERVATION_STATUS', 'THREATS', 'CLIMATE_VULNERABILITY']:
                    return 'ConservationInformation'
                elif pattern_name in ['HEIGHT', 'DIAMETER', 'GROWTH_FORM', 'LEAF_TYPE']:
                    return 'MorphologicalCharacteristics'
                elif pattern_name in ['TIMBER_VALUE', 'NON_TIMBER', 'AGROFORESTRY']:
                    return 'EconomicValue'
                elif pattern_name in ['CULTURAL_SIGNIFICANCE', 'TRADITIONAL_USES']:
                    return 'CulturalSignificance'
                elif pattern_name in ['STEWARDSHIP', 'PLANTING', 'MAINTENANCE']:
                    return 'ManagementInformation'
        
        # Default fallback logic
        if any(word in text for word in ['taxon', 'species', 'family', 'genus']):
            return 'TaxonomicRank'
        elif any(word in text for word in ['country', 'countries', 'native', 'introduced']):
            return 'GeographicDistribution'
        elif any(word in text for word in ['biome', 'habitat', 'ecological']):
            return 'EcologicalInformation'
        else:
            return 'TaxonomicRank'

    def _infer_data_type(self, text: str, option_set: str) -> str:
        if option_set and ',' in option_set:
            return 'enumeration'
        elif 'id' in text or 'taxon_id' in text:
            return 'identifier'
        elif any(word in text for word in ['height', 'diameter', 'elevation', 'min', 'max']):
            return 'numeric'
        elif 'countries' in text:
            return 'list'
        else:
            return 'string'

    def _generate_property_name(self, schema_field: str) -> str:
        """Generate camelCase property name from schema field."""
        if not schema_field:
            return "unknownProperty"
        
        # Sanitize the field name first
        safe_field = sanitize_xml_name(schema_field)
        
        # Convert to camelCase
        parts = safe_field.split('_')
        if len(parts) > 1:
            return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])
        
        return safe_field.lower()

    def _parse_enhanced_constraints(self, option_set: str, data_type: str) -> Dict[str, Any]:
        constraints = {}
        if option_set:
            delimiters = [',', ';', '|', '\n']
            values = [option_set.strip()]
            for delimiter in delimiters:
                if delimiter in option_set:
                    values = [v.strip() for v in option_set.split(delimiter) if v.strip()]
                    break
            if len(values) > 1:
                constraints['enumeration'] = values
                constraints['type'] = 'enumeration'
        return constraints

    def _creates_individuals(self, text: str, option_set: str) -> bool:
        individual_fields = ['countries', 'biomes', 'habitat', 'conservation_status']
        return any(field in text for field in individual_fields) or bool(option_set)

    def _determine_range_class(self, text: str, data_type: str) -> str:
        if 'countries' in text:
            return 'Country'
        elif 'biome' in text:
            return 'Biome'
        elif 'habitat' in text:
            return 'Habitat'
        elif 'conservation' in text:
            return 'ConservationStatus'
        elif data_type in ['string', 'numeric', 'boolean']:
            return None
        else:
            return 'Thing'

    def _is_hierarchical_field(self, text: str) -> bool:
        hierarchical_terms = ['kingdom', 'class', 'order', 'family', 'genus', 'species']
        return any(term in text for term in hierarchical_terms)

    def _is_required_field(self, exists: str, field: str) -> bool:
        if exists and exists.lower() in ['required', 'mandatory', 'yes', 'true']:
            return True
        core_fields = ['taxon_id', 'species', 'scientific_name', 'family', 'genus']
        return any(core in field.lower() for core in core_fields)

    def _determine_source_type(self, ai_category: str, manual_calc: str) -> str:
        if ai_category and manual_calc:
            return 'hybrid'
        elif ai_category:
            return 'ai_generated'
        elif manual_calc:
            return 'manual_calculation'
        else:
            return 'direct_input'

    def _generate_data_properties(self, field_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        data_properties = []
        for field_name, field_info in field_analysis.items():
            if field_info['range_class'] is None:
                prop = {
                    'name': field_info['property_name'],
                    'domain': field_info['ontology_class'],
                    'range': 'xsd:string' if field_info['data_type'] == 'string' else f"xsd:{field_info['data_type']}",
                    'functional': field_info['data_type'] in ['identifier', 'numeric'],
                    'required': field_info['required'],
                    'constraints': field_info['constraints']
                }
                data_properties.append(prop)
        return data_properties

    def _generate_object_properties_with_option_sets(self, field_analysis: Dict[str, Any], option_sets: Dict[str, Any]) -> List[Dict[str, Any]]:
        object_properties = []
        
        for field_name, field_info in field_analysis.items():
            if field_info['range_class']:
                prop = {
                    'name': field_info['property_name'],
                    'domain': field_info['ontology_class'],
                    'range': field_info['range_class'],
                    'functional': False,
                    'required': field_info['required']
                }
                object_properties.append(prop)
        
        # Add hierarchical properties
        hierarchical_properties = [
            {'name': 'hasParentTaxon', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'belongsToFamily', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'belongsToGenus', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'nativeToCountry', 'domain': 'GeographicDistribution', 'range': 'Country', 'functional': False, 'required': False},
            {'name': 'foundInBiome', 'domain': 'EcologicalInformation', 'range': 'Biome', 'functional': False, 'required': False},
            {'name': 'hasConservationStatus', 'domain': 'ConservationInformation', 'range': 'ConservationStatus', 'functional': False, 'required': False}
        ]
        
        object_properties.extend(hierarchical_properties)
        return object_properties

    def _generate_hierarchical_relationships(self, field_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        relationships = []
        hierarchy_order = ['kingdom', 'class', 'order', 'family', 'genus', 'species']
        found_levels = {}
        
        for field_name, field_info in field_analysis.items():
            for level in hierarchy_order:
                if level in field_name.lower():
                    found_levels[level] = field_name
        
        for i, level in enumerate(hierarchy_order[:-1]):
            if level in found_levels and hierarchy_order[i+1] in found_levels:
                relationships.append({
                    'type': 'taxonomic_hierarchy',
                    'parent': found_levels[level],
                    'child': found_levels[hierarchy_order[i+1]],
                    'property': 'hasParentTaxon'
                })
        
        return relationships

    def _assess_data_quality_with_option_sets(self, field_analysis: Dict[str, Any], option_sets: Dict[str, Any]) -> Dict[str, Any]:
        total_fields = len(field_analysis)
        taxonomic_fields = sum(1 for f in field_analysis.values() if f['ontology_class'] == 'TaxonomicRank')
        geographic_fields = sum(1 for f in field_analysis.values() if f['ontology_class'] == 'GeographicDistribution')
        ecological_fields = sum(1 for f in field_analysis.values() if f['ontology_class'] == 'EcologicalInformation')
        required_fields = sum(1 for f in field_analysis.values() if f['required'])
        fields_with_option_sets = sum(1 for f in field_analysis.values() if f.get('option_set_values'))
        
        return {
            'total_fields': total_fields,
            'taxonomic_fields': taxonomic_fields,
            'geographic_fields': geographic_fields,
            'ecological_fields': ecological_fields,
            'required_fields': required_fields,
            'fields_with_option_sets': fields_with_option_sets,
            'option_sets_count': len(option_sets),
            'completeness_score': min(1.0, (taxonomic_fields + geographic_fields + ecological_fields) / max(1, total_fields)),
            'taxonomic_completeness': taxonomic_fields >= 3,
            'geographic_completeness': geographic_fields >= 1,
            'ecological_completeness': ecological_fields >= 1,
            'enumeration_coverage': fields_with_option_sets / max(1, total_fields)
        }

    def _get_default_object_properties(self):
        return [
            {'name': 'hasParentTaxon', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'belongsToFamily', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'belongsToGenus', 'domain': 'TaxonomicRank', 'range': 'TaxonomicRank', 'functional': False, 'required': False},
            {'name': 'nativeToCountry', 'domain': 'GeographicDistribution', 'range': 'Country', 'functional': False, 'required': False},
            {'name': 'foundInBiome', 'domain': 'EcologicalInformation', 'range': 'Biome', 'functional': False, 'required': False},
            {'name': 'hasConservationStatus', 'domain': 'ConservationInformation', 'range': 'ConservationStatus', 'functional': False, 'required': False}
        ]

    def _generate_version_hash(self, data: List[Dict[str, Any]]) -> str:
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()[:8]

    def create_enhanced_ontology(self, analysis: Dict[str, Any], ontology_name: str = "biodiversity-ontology") -> get_ontology: # type: ignore
        """
        Create comprehensive OWL ontology with XML-safe names and content.
        """
        logger.info("Creating XML-safe enhanced multi-sheet biodiversity ontology...")
        
        # Sanitize ontology name
        safe_ontology_name = sanitize_xml_name(ontology_name)
        onto = get_ontology(f"{ONTOLOGY_IRI}#{safe_ontology_name}")
        
        with onto:
            # Create base class
            BiodiversityEntity = types.new_class("BiodiversityEntity", (Thing,))
            
            # Create ontology classes with safe names
            created_classes = {}
            for class_name, class_info in analysis['ontology_classes'].items():
                safe_class_name = sanitize_xml_name(class_name)
                logger.info(f"Creating XML-safe class: {safe_class_name}")
                
                created_classes[class_name] = types.new_class(safe_class_name, (BiodiversityEntity,))
                
                # Add safe comment
                if hasattr(created_classes[class_name], 'comment'):
                    safe_description = sanitize_xml_content(class_info['description'])
                    created_classes[class_name].comment.append(safe_description)
            
            # Create individual classes with safe names
            individual_classes = {}
            for individual in analysis['individuals']:
                class_name = individual['class']
                if class_name not in individual_classes and class_name != 'Thing':
                    safe_class_name = sanitize_xml_name(class_name)
                    logger.info(f"Creating XML-safe individual class: {safe_class_name}")
                    individual_classes[class_name] = types.new_class(safe_class_name, (Thing,))
            
            # Create data properties with safe names
            for prop in analysis['data_properties']:
                safe_prop_name = sanitize_xml_name(prop['name'])
                logger.info(f"Creating XML-safe data property: {safe_prop_name}")
                
                domain_class = created_classes.get(prop['domain'], BiodiversityEntity)
                
                try:
                    if prop.get('functional'):
                        data_prop = types.new_class(safe_prop_name, (DataProperty, FunctionalProperty))
                    else:
                        data_prop = types.new_class(safe_prop_name, (DataProperty,))
                    
                    data_prop.domain.append(domain_class)
                    
                    # Set range safely
                    if 'string' in prop['range']:
                        data_prop.range.append(str)
                    elif 'decimal' in prop['range'] or 'numeric' in prop['range']:
                        data_prop.range.append(float)
                    elif 'integer' in prop['range']:
                        data_prop.range.append(int)
                    elif 'boolean' in prop['range']:
                        data_prop.range.append(bool)
                        
                except Exception as e:
                    logger.error(f"Error creating data property {safe_prop_name}: {str(e)}")
            
            # Create object properties with safe names
            for prop in analysis['object_properties']:
                safe_prop_name = sanitize_xml_name(prop['name'])
                logger.info(f"Creating XML-safe object property: {safe_prop_name}")
                
                domain_class = created_classes.get(prop['domain'], BiodiversityEntity)
                range_class = individual_classes.get(prop['range']) or created_classes.get(prop['range'], Thing)
                
                try:
                    obj_prop = types.new_class(safe_prop_name, (ObjectProperty,))
                    obj_prop.domain.append(domain_class)
                    obj_prop.range.append(range_class)
                except Exception as e:
                    logger.error(f"Error creating object property {safe_prop_name}: {str(e)}")
            
            # Create named individuals with XML-safe names
            created_individuals = 0
            for individual in analysis['individuals']:
                if individual['class'] in individual_classes:
                    safe_individual_name = individual['name']  # Already sanitized
                    individual_class = individual_classes[individual['class']]
                    
                    try:
                        logger.info(f"Creating XML-safe individual: {safe_individual_name} ({individual['class']})")
                        named_individual = individual_class(safe_individual_name)
                        
                        # Add safe label
                        if hasattr(named_individual, 'label'):
                            safe_label = sanitize_xml_content(individual['label'])
                            named_individual.label.append(safe_label)
                        
                        # Add safe comment
                        if hasattr(named_individual, 'comment'):
                            safe_comment = sanitize_xml_content(f"From {individual['source_field']} option set")
                            named_individual.comment.append(safe_comment)
                        
                        created_individuals += 1
                        
                    except Exception as e:
                        logger.error(f"Error creating individual {safe_individual_name}: {str(e)}")
        
        logger.info(f"XML-safe enhanced multi-sheet ontology creation complete:")
        logger.info(f"  • Classes: {len(created_classes)}")
        logger.info(f"  • Individual Classes: {len(individual_classes)}")
        logger.info(f"  • Data Properties: {len(analysis['data_properties'])}")
        logger.info(f"  • Object Properties: {len(analysis['object_properties'])}")
        logger.info(f"  • Named Individuals: {created_individuals}")
        
        return onto

    def generate_enhanced_ontology_from_directory(self, directory_path: str, ontology_name: str = "biodiversity-ontology") -> str:
        """Complete pipeline: analyze multi-sheet directory and generate ontology."""
        logger.info(f"Starting enhanced multi-sheet biodiversity ontology generation from {directory_path}")
        
        # Analyze the directory
        analysis = self.analyze_multi_sheet_directory(directory_path)
        
        # Create enhanced ontology
        onto = self.create_enhanced_ontology(analysis, ontology_name)
        
        # Save ontology
        output_file = f"{ontology_name}.owl"
        logger.info(f"Saving enhanced multi-sheet ontology to {output_file}")
        onto.save(file=output_file, format="rdfxml")
        
        # Print comprehensive summary
        self._print_multi_sheet_analysis_summary(analysis)
        
        logger.info(f"Enhanced multi-sheet biodiversity ontology generation complete: {output_file}")
        return output_file

    def _print_multi_sheet_analysis_summary(self, analysis: Dict[str, Any]) -> None:
        """Print detailed summary of multi-sheet analysis."""
        print("\n" + "="*60)
        print("🌲 MULTI-SHEET BIODIVERSITY ONTOLOGY ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"📊 Total Fields Analyzed: {len(analysis['field_analysis'])}")
        print(f"🏗️  Ontology Classes Created: {len(analysis['ontology_classes'])}")
        print(f"📝 Data Properties: {len(analysis['data_properties'])}")
        print(f"🔗 Object Properties: {len(analysis['object_properties'])}")
        print(f"👤 Named Individuals: {len(analysis['individuals'])}")
        print(f"🎯 Option Sets: {len(analysis['option_sets'])}")
        
        print(f"\n🏷️  ONTOLOGY CLASSES:")
        for class_name, class_info in analysis['ontology_classes'].items():
            print(f"   • {class_name}: {len(class_info['fields'])} fields")
            for field in class_info['fields'][:3]:
                print(f"     - {field}")
            if len(class_info['fields']) > 3:
                print(f"     ... and {len(class_info['fields']) - 3} more")
        
        print(f"\n🎯 OPTION SETS:")
        for field_name, option_data in analysis['option_sets'].items():
            print(f"   • {field_name}: {option_data['count']} values")
            if 'values' in option_data:
                for value in option_data['values'][:3]:
                    print(f"     - {value}")
                if len(option_data['values']) > 3:
                    print(f"     ... and {len(option_data['values']) - 3} more")
        
        print(f"\n👥 NAMED INDIVIDUALS BY CLASS:")
        individuals_by_class = {}
        for individual in analysis['individuals']:
            class_name = individual['class']
            if class_name not in individuals_by_class:
                individuals_by_class[class_name] = []
            individuals_by_class[class_name].append(individual['label'])
        
        for class_name, individuals in individuals_by_class.items():
            print(f"   • {class_name}: {len(individuals)} individuals")
            for individual in individuals[:3]:
                print(f"     - {individual}")
            if len(individuals) > 3:
                print(f"     ... and {len(individuals) - 3} more")
        
        quality = analysis['data_quality']
        print(f"\n📈 ENHANCED DATA QUALITY ASSESSMENT:")
        print(f"   • Completeness Score: {quality['completeness_score']:.2f}")
        print(f"   • Enumeration Coverage: {quality['enumeration_coverage']:.2f}")
        print(f"   • Taxonomic Fields: {quality['taxonomic_fields']}")
        print(f"   • Geographic Fields: {quality['geographic_fields']}")
        print(f"   • Ecological Fields: {quality['ecological_fields']}")
        print(f"   • Fields with Option Sets: {quality['fields_with_option_sets']}")
        print(f"   • Taxonomic Complete: {'✅' if quality['taxonomic_completeness'] else '❌'}")
        print(f"   • Geographic Complete: {'✅' if quality['geographic_completeness'] else '❌'}")
        print(f"   • Ecological Complete: {'✅' if quality['ecological_completeness'] else '❌'}")

    def get_multi_sheet_analysis_summary(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get structured summary of multi-sheet analysis results."""
        return {
            'version': analysis.get('version'),
            'timestamp': analysis.get('timestamp'),
            'total_fields': len(analysis.get('field_analysis', {})),
            'ontology_classes': list(analysis.get('ontology_classes', {}).keys()),
            'data_properties_count': len(analysis.get('data_properties', [])),
            'object_properties_count': len(analysis.get('object_properties', [])),
            'individuals_count': len(analysis.get('individuals', [])),
            'option_sets_count': len(analysis.get('option_sets', {})),
            'hierarchical_relationships_count': len(analysis.get('hierarchical_relationships', [])),
            'data_quality': analysis.get('data_quality', {}),
            'categories': analysis.get('categories', {}),
            'field_distribution': {
                class_name: len(fields) for class_name, fields in analysis.get('categories', {}).items()
            },
            'multi_sheet_features': {
                'mvp_processing': True,
                'option_set_integration': True,
                'named_individuals_from_enums': True,
                'enhanced_constraints': True
            }
        }


# Convenience function for directory processing
def generate_multi_sheet_biodiversity_ontology_from_directory(directory_path: str, ontology_name: str = "biodiversity-ontology") -> str:
    """
    Generate enhanced biodiversity ontology from directory containing MVP + Option Set CSV files.
    """
    original_dir = os.getcwd()
    os.chdir(directory_path)
    
    try:
        generator = MultiSheetBiodiversityGenerator()
        return generator.generate_enhanced_ontology_from_directory(".", ontology_name)
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    # Test the multi-sheet generator
    generator = MultiSheetBiodiversityGenerator()
    
    print("🌲 Multi-Sheet Biodiversity Ontology Generator")
    print("=" * 60)
    print("This generator handles:")
    print("✅ MVP sheet with field definitions")
    print("✅ Option Set sheet with enumerated values")
    print("✅ Named individuals from option sets")
    print("✅ Enhanced constraints and relationships")
    print("✅ Comprehensive biodiversity ontologies")
    
    # Test with current directory
    try:
        ontology_file = generate_multi_sheet_biodiversity_ontology_from_directory(".", "test-multi-sheet-biodiversity")
        print(f"\n✅ Successfully generated: {ontology_file}")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("Make sure you have CSV files in the current directory")