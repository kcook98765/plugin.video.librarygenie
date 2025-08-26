#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Enhanced Year Parser
Robust year parsing with explicit rules and edge case handling
"""

import re
from typing import Optional, Tuple, Union
from ..utils.logger import get_logger


class YearParser:
    """Enhanced year parser with robust edge case handling"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Enhanced regex patterns for year parsing
        # Explicit prefixes always treated as year filters
        self.explicit_year_pattern = re.compile(
            r'\b(?:y|year):(\d{4})\b', re.IGNORECASE
        )
        self.explicit_year_range_pattern = re.compile(
            r'\b(?:y|year):(\d{4})[-–—](\d{4})\b', re.IGNORECASE
        )
        self.explicit_year_comparison_pattern = re.compile(
            r'\b(?:y|year)(>=|<=|>|<)(\d{4})\b', re.IGNORECASE
        )
        
        # Isolated 4-digit years (with word boundaries)
        self.isolated_year_pattern = re.compile(r'\b(19|20)\d{2}\b')
        
        # Year ranges without explicit prefix
        self.year_range_pattern = re.compile(r'\b(19|20)\d{2}[-–—\.\.](19|20)\d{2}\b')
        
        # Decade shorthand patterns (90s, '90s, 1990s)
        self.decade_shorthand_pattern = re.compile(
            r"\b(?:'?(\d{2})s|(\d{4})s)\b", re.IGNORECASE
        )
        
        # Patterns that should NOT be treated as years (title parts)
        self.title_number_patterns = [
            re.compile(r'\b\d{4}:\s*[a-zA-Z]'),  # "2001: A Space Odyssey"
            re.compile(r'\b[a-zA-Z]+\s+\d{4}\b'),  # "Fahrenheit 451", "Area 51"
            re.compile(r'\b\d{4}\s*[a-zA-Z]'),  # "2012Apocalypse" (no space)
        ]
    
    def parse_year_filter(self, text: str, enable_decade_shorthand: bool = False) -> Optional[Union[int, Tuple[int, int]]]:
        """
        Parse year filter from text with explicit rules:
        1. Explicit prefixes (y:, year:) always treated as filters
        2. Isolated 4-digit years may be treated as years
        3. Numbers in titles are NOT treated as years unless prefixed
        """
        if not text:
            return None
        
        try:
            # 1. Check for explicit year prefixes first (highest priority)
            explicit_result = self._parse_explicit_year_filters(text)
            if explicit_result:
                return explicit_result
            
            # 2. Check for decade shorthand if enabled
            if enable_decade_shorthand:
                decade_result = self._parse_decade_shorthand(text)
                if decade_result:
                    return decade_result
            
            # 3. Check for year ranges (isolated)
            range_result = self._parse_year_ranges(text)
            if range_result:
                return range_result
            
            # 4. Check for isolated years (with title protection)
            isolated_result = self._parse_isolated_years(text)
            if isolated_result:
                return isolated_result
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error parsing year filter from '{text}': {e}")
            return None
    
    def _parse_explicit_year_filters(self, text: str) -> Optional[Union[int, Tuple[int, int]]]:
        """Parse explicit year filters with prefixes"""
        try:
            # Check for comparison operators (y>=1990, year<=2005)
            comp_match = self.explicit_year_comparison_pattern.search(text)
            if comp_match:
                operator = comp_match.group(1)
                year = int(comp_match.group(2))
                
                if operator == '>=':
                    return (year, 2099)  # From year to future
                elif operator == '>':
                    return (year + 1, 2099)  # From year+1 to future
                elif operator == '<=':
                    return (1900, year)  # From past to year
                elif operator == '<':
                    return (1900, year - 1)  # From past to year-1
            
            # Check for explicit ranges (y:1999-2003, year:1990-1995)
            range_match = self.explicit_year_range_pattern.search(text)
            if range_match:
                start_year = int(range_match.group(1))
                end_year = int(range_match.group(2))
                if start_year <= end_year and 1900 <= start_year <= 2099 and 1900 <= end_year <= 2099:
                    return (start_year, end_year)
                else:
                    # Invalid range, fallback to single year (first one)
                    return start_year if 1900 <= start_year <= 2099 else None
            
            # Check for explicit single years (y:1999, year:2010)
            year_match = self.explicit_year_pattern.search(text)
            if year_match:
                year = int(year_match.group(1))
                if 1900 <= year <= 2099:
                    return year
            
            return None
            
        except Exception:
            return None
    
    def _parse_decade_shorthand(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse decade shorthand like '90s', 1990s"""
        try:
            match = self.decade_shorthand_pattern.search(text)
            if match:
                if match.group(1):  # '90s format
                    decade = int(match.group(1))
                    if decade <= 30:  # 00s-30s = 2000s-2030s
                        start_year = 2000 + decade
                    else:  # 40s-99s = 1940s-1990s
                        start_year = 1900 + decade
                    return (start_year, start_year + 9)
                elif match.group(2):  # 1990s format
                    century_year = int(match.group(2))
                    if century_year % 10 == 0:  # Must be decade year (1990, 2000, etc.)
                        return (century_year, century_year + 9)
            
            return None
            
        except Exception:
            return None
    
    def _parse_year_ranges(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse year ranges like 1999-2003"""
        try:
            # Check if this range is part of a title (protected)
            if self._is_part_of_title(text):
                return None
            
            match = self.year_range_pattern.search(text)
            if match:
                range_str = match.group()
                # Split on various dash characters
                parts = re.split(r'[-–—]|\.\.', range_str)
                if len(parts) == 2:
                    start_year = int(parts[0])
                    end_year = int(parts[1])
                    if start_year <= end_year and 1900 <= start_year <= 2099 and 1900 <= end_year <= 2099:
                        return (start_year, end_year)
            
            return None
            
        except Exception:
            return None
    
    def _parse_isolated_years(self, text: str) -> Optional[int]:
        """Parse isolated 4-digit years with title protection"""
        try:
            # Check if any years are part of titles (protected)
            if self._is_part_of_title(text):
                return None
            
            # Find all isolated years
            year_matches = list(self.isolated_year_pattern.finditer(text))
            if len(year_matches) == 1:
                # Exactly one isolated year - safe to use
                year_str = year_matches[0].group()
                year = int(year_str)
                if 1900 <= year <= 2099:
                    return year
            
            # Multiple years or no years - too ambiguous
            return None
            
        except Exception:
            return None
    
    def _is_part_of_title(self, text: str) -> bool:
        """Check if years in text are part of movie titles"""
        try:
            # Check against known title patterns
            for pattern in self.title_number_patterns:
                if pattern.search(text):
                    return True
            
            # Additional checks for common title patterns
            text_lower = text.lower()
            
            # Common movie title patterns with years - be very specific
            protected_patterns = [
                '2001: a space odyssey',
                '2001:a space odyssey', 
                'fahrenheit 451',
                'area 51',
                'apollo 13',
                'district 9',
                'studio 54',
                'route 66',
                'highway 61',
                'catch 22',
                "ocean's 11",
                "ocean's 12", 
                "ocean's 13"
            ]
            
            # Only protect if exact title match
            for protected in protected_patterns:
                if protected == text_lower.strip():
                    return True
            
            return False
            
        except Exception:
            return False
    
    def remove_year_filters_from_text(self, text: str) -> str:
        """Remove detected year filters from text, leaving clean search terms"""
        try:
            original_text = text
            
            # Remove explicit year filters
            text = self.explicit_year_pattern.sub(' ', text)
            text = self.explicit_year_range_pattern.sub(' ', text)
            text = self.explicit_year_comparison_pattern.sub(' ', text)
            
            # Remove decade shorthand if it's not part of a title
            if not self._is_part_of_title(original_text):
                text = self.decade_shorthand_pattern.sub(' ', text)
            
            # Remove isolated year ranges if not part of title
            if not self._is_part_of_title(original_text):
                text = self.year_range_pattern.sub(' ', text)
                
                # Remove isolated single years (more conservative)
                year_matches = list(self.isolated_year_pattern.finditer(text))
                if len(year_matches) == 1:  # Only if exactly one year
                    text = self.isolated_year_pattern.sub(' ', text)
            
            # Clean up extra spaces
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
            
        except Exception:
            return text


# Global year parser instance
_year_parser_instance = None


def get_year_parser():
    """Get global year parser instance"""
    global _year_parser_instance
    if _year_parser_instance is None:
        _year_parser_instance = YearParser()
    return _year_parser_instance