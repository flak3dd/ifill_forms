import io
import csv
import polars as pl
import pandas as pd
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
from .schemas import FileAnalysis, ColumnInfo

logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls', '.json']
    
    async def analyze_file(self, content: bytes, filename: str) -> FileAnalysis:
        """Analyze uploaded file and return metadata"""
        try:
            file_ext = filename.lower().split('.')[-1]
            
            if file_ext == 'csv':
                df = pl.read_csv(io.BytesIO(content))
            elif file_ext in ['xlsx', 'xls']:
                df = pl.read_excel(io.BytesIO(content))
            elif file_ext == 'json':
                df = pl.read_json(io.BytesIO(content))
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
            
            # Get column information
            columns = []
            for col_name in df.columns:
                column_data = df[col_name]
                
                # Determine column type
                dtype = str(column_data.dtype)
                if dtype in ['i64', 'i32', 'f64', 'f32']:
                    col_type = 'numeric'
                elif dtype == 'bool':
                    col_type = 'boolean'
                elif dtype == 'date':
                    col_type = 'date'
                else:
                    col_type = 'text'
                
                # Get sample values (non-null)
                sample_values = column_data.drop_nulls().head(5).to_list()
                sample_values = [str(val) for val in sample_values if val is not None]
                
                column_info = ColumnInfo(
                    name=col_name,
                    type=col_type,
                    sample_values=sample_values,
                    null_count=column_data.null_count(),
                    unique_count=column_data.n_unique()
                )
                columns.append(column_info)
            
            # Get sample data (first 10 rows)
            sample_data = df.head(10).to_dicts()
            
            # Validate data
            validation_errors = self._validate_data(df)
            
            return FileAnalysis(
                filename=filename,
                total_rows=len(df),
                total_columns=len(df.columns),
                columns=columns,
                sample_data=sample_data,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            logger.error(f"File analysis error: {str(e)}")
            raise ValueError(f"Failed to analyze file: {str(e)}")
    
    def _validate_data(self, df: pl.DataFrame) -> List[str]:
        """Validate data and return list of errors"""
        errors = []
        
        # Check for empty dataframe
        if len(df) == 0:
            errors.append("File contains no data rows")
            return errors
        
        # Check for empty columns
        for col in df.columns:
            if df[col].null_count() == len(df):
                errors.append(f"Column '{col}' is completely empty")
        
        # Check for duplicate columns
        if len(df.columns) != len(set(df.columns)):
            errors.append("File contains duplicate column names")
        
        # Check for reasonable row count
        if len(df) > 100000:
            errors.append(f"File contains {len(df)} rows, which may exceed processing limits")
        
        return errors
    
    async def process_data(self, file_path: str, mappings: Dict[str, Any], 
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Process data file with field mappings and filters"""
        try:
            # Read the file
            if file_path.endswith('.csv'):
                df = pl.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pl.read_excel(file_path)
            else:
                raise ValueError("Unsupported file format")
            
            # Apply filters if provided
            if filters:
                df = self._apply_filters(df, filters)
            
            # Apply transformations based on mappings
            df = self._apply_transformations(df, mappings)
            
            # Convert to list of dictionaries
            data = df.to_dicts()
            
            # Add row index for tracking
            for i, row in enumerate(data):
                row['_row_index'] = i
            
            return data
            
        except Exception as e:
            logger.error(f"Data processing error: {str(e)}")
            raise ValueError(f"Failed to process data: {str(e)}")
    
    def _apply_filters(self, df: pl.DataFrame, filters: Dict[str, Any]) -> pl.DataFrame:
        """Apply row filters to dataframe"""
        for column, filter_config in filters.items():
            if column not in df.columns:
                continue
            
            filter_type = filter_config.get('type', 'equals')
            value = filter_config.get('value')
            
            if filter_type == 'equals':
                df = df.filter(pl.col(column) == value)
            elif filter_type == 'not_equals':
                df = df.filter(pl.col(column) != value)
            elif filter_type == 'contains':
                df = df.filter(pl.col(column).str.contains(str(value)))
            elif filter_type == 'not_contains':
                df = df.filter(~pl.col(column).str.contains(str(value)))
            elif filter_type == 'greater_than':
                df = df.filter(pl.col(column) > value)
            elif filter_type == 'less_than':
                df = df.filter(pl.col(column) < value)
            elif filter_type == 'is_not_null':
                df = df.filter(pl.col(column).is_not_null())
            elif filter_type == 'is_null':
                df = df.filter(pl.col(column).is_null())
        
        return df
    
    def _apply_transformations(self, df: pl.DataFrame, mappings: Dict[str, Any]) -> pl.DataFrame:
        """Apply data transformations based on field mappings"""
        for csv_column, mapping in mappings.items():
            if csv_column not in df.columns:
                continue
            
            transformation = mapping.get('transformation')
            
            if transformation == 'title_case':
                df = df.with_columns(
                    pl.col(csv_column).str.title().alias(csv_column)
                )
            elif transformation == 'upper_case':
                df = df.with_columns(
                    pl.col(csv_column).str.to_uppercase().alias(csv_column)
                )
            elif transformation == 'lower_case':
                df = df.with_columns(
                    pl.col(csv_column).str.to_lowercase().alias(csv_column)
                )
            elif transformation == 'phone_format':
                df = df.with_columns(
                    pl.col(csv_column).map_elements(
                        lambda x: self._format_phone(str(x)) if x else x
                    ).alias(csv_column)
                )
            elif transformation == 'email_clean':
                df = df.with_columns(
                    pl.col(csv_column).str.strip().str.to_lowercase().alias(csv_column)
                )
            elif transformation == 'date_format':
                target_format = mapping.get('target_format', '%Y-%m-%d')
                df = df.with_columns(
                    pl.col(csv_column).str.strptime(pl.Date, format='%Y-%m-%d').dt.strftime(target_format).alias(csv_column)
                )
        
        return df
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number string"""
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        return phone
    
    async def validate_mapping(self, mappings: Dict[str, Any], 
                              file_columns: List[str]) -> Dict[str, Any]:
        """Validate field mappings against file columns"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "unmapped_columns": [],
            "unmapped_required_fields": []
        }
        
        # Check for unmapped columns
        mapped_columns = set(mappings.keys())
        all_columns = set(file_columns)
        validation_result["unmapped_columns"] = list(all_columns - mapped_columns)
        
        # Check for mappings to non-existent columns
        for csv_column in mappings.keys():
            if csv_column not in all_columns:
                validation_result["errors"].append(f"Mapping references non-existent column: {csv_column}")
                validation_result["valid"] = False
        
        # Check required fields (this would depend on profile requirements)
        # For now, just warn about unmapped columns
        if validation_result["unmapped_columns"]:
            validation_result["warnings"].append(
                f"{len(validation_result['unmapped_columns'])} columns are not mapped"
            )
        
        return validation_result
    
    async def generate_sample_data(self, num_rows: int = 5) -> List[Dict[str, Any]]:
        """Generate sample data for testing"""
        sample_data = []
        
        for i in range(num_rows):
            row = {
                "firstName": f"Test{i}",
                "lastName": f"User{i}",
                "email": f"test{i}@example.com",
                "phone": f"555-010{i}",
                "address": f"{100 + i} Test St",
                "city": "Test City",
                "state": "TS",
                "zip": f"1000{i}",
                "jobTitle": f"Test Position {i}",
                "company": f"Test Company {i}",
                "experience": f"{i + 1} years",
                "education": "Bachelor's Degree",
                "skills": f"skill1, skill2, skill{i}",
                "salary": f"5000{i}",
                "availability": "Immediate",
                "coverLetter": f"This is a sample cover letter for position {i}."
            }
            sample_data.append(row)
        
        return sample_data
