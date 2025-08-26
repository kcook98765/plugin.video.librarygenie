#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Kodi Module
Kodi-specific functionality and API clients
"""

from .json_rpc_client import get_kodi_client

__all__ = ["get_kodi_client"]