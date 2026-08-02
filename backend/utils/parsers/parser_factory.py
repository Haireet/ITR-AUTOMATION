"""
Parser factory - creates appropriate parser based on file type
"""
import os
from typing import Optional

from .base_parser import BaseParser, ParseResult
from .csv_parser import CSVParser
from .excel_parser import ExcelParser
from .pdf_parser import PDFParser


class ParserFactory:
    """Factory class to create appropriate parser based on file type"""
    
    @staticmethod
    def get_parser(file_path: str, file_type: Optional[str] = None) -> BaseParser:
        """
        Get appropriate parser for the file
        
        Args:
            file_path: Path to the file
            file_type: MIME type of the file (optional)
        
        Returns:
            Appropriate parser instance
        
        Raises:
            ValueError: If file type is not supported
        """
        # Get file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Determine parser based on extension or MIME type
        if file_extension == '.csv' or file_type == 'text/csv':
            return CSVParser()
        
        elif file_extension in ['.xls', '.xlsx'] or \
             file_type in ['application/vnd.ms-excel', 
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            return ExcelParser()
        
        elif file_extension == '.pdf' or file_type == 'application/pdf':
            return PDFParser()
        
        else:
            raise ValueError(f"Unsupported file type: {file_extension or file_type}")
    
    @staticmethod
    def parse_statement(file_path: str, file_type: Optional[str] = None, password: Optional[str] = None) -> ParseResult:
        """
        Parse bank statement using appropriate parser
        
        Args:
            file_path: Path to the file
            file_type: MIME type of the file (optional)
            password: Password for encrypted PDFs (optional)
        
        Returns:
            ParseResult with transactions and metadata
        """
        try:
            parser = ParserFactory.get_parser(file_path, file_type)
            return parser.parse(file_path, password=password)
        except Exception as e:
            from .base_parser import StatementMetadata
            return ParseResult(
                transactions=[],
                metadata=StatementMetadata(),
                success=False,
                error_message=f"Failed to parse statement: {str(e)}"
            )
