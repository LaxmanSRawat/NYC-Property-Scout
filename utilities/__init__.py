"""
Utilities package for NYC Rent Web Scraper.

This package contains utility modules for various operations
such as uploading data to IBM Cloudant database.
"""

from .cloudant_uploader import CloudantUploader

__all__ = ["CloudantUploader"]
