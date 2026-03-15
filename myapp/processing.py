"""
processing.py — Your custom logic goes here.

This module receives:
  - df: a pandas DataFrame (the uploaded CSV)
  - choices: a dict of user selections from the form

It returns a dict that is displayed on the Results page.

Replace the placeholder logic below with your real business rules.
"""

import pandas as pd


def process(df: pd.DataFrame, choices: dict) -> dict:
    """
    Main processing function. Receives the uploaded CSV as a DataFrame
    and the user's choices as a dictionary.

    Returns a dict with at least:
      - 'summary': str — a short text summary shown at the top
      - 'table': list of dicts — rows to display in a results table
      - 'stats': dict — any key/value stats to highlight
    """

    # ----------------------------------------------------------------
    # PLACEHOLDER LOGIC — replace everything below with your own rules
    # ----------------------------------------------------------------

    summary = (
        f"Processed {len(df)} rows with {len(df.columns)} columns. "
        f"User selected: {choices}."
    )

    # Example: return first 20 rows as a preview table
    table = df.head(20).fillna('').to_dict(orient='records')

    # Example: basic stats per numeric column
    stats = {}
    for col in df.select_dtypes(include='number').columns:
        stats[col] = {
            'min': round(df[col].min(), 2),
            'max': round(df[col].max(), 2),
            'mean': round(df[col].mean(), 2),
        }

    return {
        'summary': summary,
        'table': table,
        'columns': list(df.columns),
        'stats': stats,
        'choices': choices,
    }


def get_choice_options(df: pd.DataFrame) -> list:
    """
    Given a freshly uploaded DataFrame, return a list of choice
    definitions to show the user before processing.

    Each item is a dict:
      {
        'name':    str   — form field name,
        'label':   str   — human-readable label,
        'type':    str   — 'select' | 'multiselect' | 'checkbox' | 'text',
        'options': list  — list of option strings (for select/multiselect),
        'default': any   — default value (optional),
      }

    Replace the examples below with your real choices.
    """
    columns = list(df.columns)

    return [
        {
            'name': 'group_by',
            'label': 'Group results by column',
            'type': 'select',
            'options': ['(none)'] + columns,
            'default': '(none)',
        },
        {
            'name': 'filter_mode',
            'label': 'Filter mode',
            'type': 'select',
            'options': ['All rows', 'Non-empty rows only', 'First 100 rows'],
            'default': 'All rows',
        },
        {
            'name': 'include_stats',
            'label': 'Include numeric statistics',
            'type': 'checkbox',
            'options': [],
            'default': True,
        },
    ]
