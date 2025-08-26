#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Phase 12 Remote Integration
Optional remote API integration with privacy-first design
"""

from .http_client import RemoteHTTPClient
from .service import RemoteService
from .mapper import RemoteMapper
from .cache import RemoteCache

__all__ = [
    'RemoteHTTPClient',
    'RemoteService', 
    'RemoteMapper',
    'RemoteCache'
]