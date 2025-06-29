"""
Unified Scraping Module

This module provides a unified interface for all web scraping operations,
consolidating Crawl4AI integration and other scraping capabilities.
"""

from .unified_scraper import UnifiedScraper, ScrapingResult

__all__ = [
    "UnifiedScraper",
    "ScrapingResult",
] 