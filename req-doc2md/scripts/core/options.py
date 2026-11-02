"""Conversion options shared by the converters."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Options:
    link_style: str = 'obsidian'          # obsidian | standard
    table_format: str = 'auto'            # auto | pipe | html
    heading_number: bool = True
    strict: bool = False
    nested: bool = False
    keep_temp: bool = False
    max_depth: int = 5
    max_rows: int = 2000
    max_cols: int = 200
