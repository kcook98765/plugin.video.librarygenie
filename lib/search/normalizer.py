#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Unified Text Normalizer
Consistent text normalization for both indexing and querying
"""

import re
import unicodedata
from typing import List


class TextNormalizer:
    """Unified text normalizer for consistent indexing and querying"""
    
    def __init__(self):
        # Precompiled regex patterns for efficiency
        self._punctuation_pattern = re.compile(r'[^\w\s]')
        self._whitespace_pattern = re.compile(r'\s+')
        self._hyphen_pattern = re.compile(r'[-–—_]')
    
    def normalize(self, text: str) -> str:
        """
        Normalize text using deterministic, language-agnostic rules:
        1. Unicode NFKD normalize, remove diacritics
        2. Lowercase with casefold()
        3. Replace punctuation and hyphens with single space
        4. Collapse multiple spaces and trim
        """
        if not text:
            return ""
        
        try:
            # 1. Unicode NFKD normalize and remove diacritics
            # NFKD decomposes characters, then we filter out combining characters
            normalized = unicodedata.normalize('NFKD', text)
            # Remove diacritics (combining characters) - category Mn and Mc
            normalized = ''.join(
                char for char in normalized 
                if unicodedata.category(char) not in ('Mn', 'Mc')
            )
            
            # 2. Lowercase with casefold() (more aggressive than lower())
            normalized = normalized.casefold()
            
            # 3. Replace hyphens and underscores with spaces first
            normalized = self._hyphen_pattern.sub(' ', normalized)
            
            # 4. Replace all punctuation with spaces
            normalized = self._punctuation_pattern.sub(' ', normalized)
            
            # 5. Collapse multiple spaces and trim
            normalized = self._whitespace_pattern.sub(' ', normalized).strip()
            
            return normalized
            
        except Exception:
            # Fallback to basic normalization
            return text.lower().strip() if text else ""
    
    def normalize_tokens(self, text: str) -> List[str]:
        """
        Normalize text and split into tokens
        """
        normalized = self.normalize(text)
        if not normalized:
            return []
        
        # Split on whitespace and filter out empty tokens
        tokens = [token for token in normalized.split() if token]
        return tokens


# Global normalizer instance for consistent usage
_text_normalizer_instance = None


def get_text_normalizer():
    """Get global text normalizer instance"""
    global _text_normalizer_instance
    if _text_normalizer_instance is None:
        _text_normalizer_instance = TextNormalizer()
    return _text_normalizer_instance