"""
Report saver module for persisting AI analysis results to __reports__ directory.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Get the project root directory (parent of app directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "__reports__"
PROMISE_SCORE_DIR = REPORTS_DIR / "promise-score"
DUE_DILIGENCE_DIR = REPORTS_DIR / "due-diligence"


def _ensure_directories() -> None:
    """Create report directories if they don't exist."""
    PROMISE_SCORE_DIR.mkdir(parents=True, exist_ok=True)
    DUE_DILIGENCE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_filename(report_type: str, **kwargs: Any) -> str:
    """
    Generate a unique filename for the report.
    
    Args:
        report_type: Type of report ('promise-score' or 'due-diligence')
        **kwargs: Context-specific parameters for the filename
        
    Returns:
        Filename string with format: YYYYMMDD_HHMMSS_{context}.json
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if report_type == "promise-score":
        quarter = kwargs.get("quarter", "unknown")
        top_n = kwargs.get("top_n", "all")
        return f"{timestamp}_{quarter}_top{top_n}.json"
    elif report_type == "due-diligence":
        ticker = kwargs.get("ticker", "unknown")
        quarter = kwargs.get("quarter", "unknown")
        return f"{timestamp}_{ticker}_{quarter}.json"
    else:
        return f"{timestamp}.json"


def save_promise_score_report(
    quarter: str,
    top_n: int,
    df: pd.DataFrame,
    model_id: str | None = None,
    provider_id: str | None = None,
    weights: dict | None = None,
) -> str:
    """
    Save a Promise Score analysis report.
    
    Args:
        quarter: Quarter identifier (e.g., "2025Q1")
        top_n: Number of top stocks analyzed
        df: DataFrame with ranked stocks and scores
        model_id: Optional model identifier
        provider_id: Optional provider identifier
        weights: Optional AI-selected weights used
        
    Returns:
        Path to the saved report file
    """
    _ensure_directories()
    
    filename = _generate_filename("promise-score", quarter=quarter, top_n=top_n)
    filepath = PROMISE_SCORE_DIR / filename
    
    # Convert DataFrame to list of dicts
    stocks = df.to_dict(orient="records")
    
    # Build report structure
    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "quarter": quarter,
            "top_n": top_n,
            "model_id": model_id,
            "provider_id": provider_id,
        },
        "weights": weights or {},
        "stocks": stocks,
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    return str(filepath)


def save_due_diligence_report(
    ticker: str,
    quarter: str,
    result: dict,
    model_id: str | None = None,
    provider_id: str | None = None,
) -> str:
    """
    Save a Stock Due Diligence report.
    
    Args:
        ticker: Stock ticker symbol
        quarter: Quarter identifier (e.g., "2025Q1")
        result: Dictionary containing AI analysis results
        model_id: Optional model identifier
        provider_id: Optional provider identifier
        
    Returns:
        Path to the saved report file
    """
    _ensure_directories()
    
    filename = _generate_filename("due-diligence", ticker=ticker, quarter=quarter)
    filepath = DUE_DILIGENCE_DIR / filename
    
    # Build report structure
    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "ticker": ticker,
            "quarter": quarter,
            "model_id": model_id,
            "provider_id": provider_id,
        },
        **result,
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    return str(filepath)


def list_reports(report_type: str) -> list[dict]:
    """
    List all saved reports of a specific type.
    
    Args:
        report_type: Type of report ('promise-score' or 'due-diligence')
        
    Returns:
        List of report metadata dictionaries, sorted by generation time (newest first)
    """
    if report_type == "promise-score":
        directory = PROMISE_SCORE_DIR
    elif report_type == "due-diligence":
        directory = DUE_DILIGENCE_DIR
    else:
        return []
    
    if not directory.exists():
        return []
    
    reports = []
    for filepath in directory.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = json.load(f)
            
            metadata = content.get("metadata", {})
            reports.append({
                "filename": filepath.name,
                "filepath": str(filepath),
                "generated_at": metadata.get("generated_at", ""),
                "quarter": metadata.get("quarter", ""),
                "ticker": metadata.get("ticker"),
                "top_n": metadata.get("top_n"),
                "model_id": metadata.get("model_id"),
                "provider_id": metadata.get("provider_id"),
            })
        except (json.JSONDecodeError, IOError):
            continue
    
    # Sort by generated_at descending (newest first)
    reports.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    
    return reports


def get_report(filepath: str) -> dict:
    """
    Load a specific report by filepath.
    
    Args:
        filepath: Full path to the report file
        
    Returns:
        Report content as dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {filepath}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_report(filepath: str) -> bool:
    """
    Delete a specific report file.
    
    Args:
        filepath: Full path to the report file
        
    Returns:
        True if deletion was successful
        
    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be deleted
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {filepath}")
    
    path.unlink()
    return True


def get_report_filename(filepath: str) -> str:
    """
    Extract just the filename from a filepath.
    
    Args:
        filepath: Full path to the report file
        
    Returns:
        Filename string
    """
    return Path(filepath).name


def format_relative_time(iso_timestamp: str) -> str:
    """
    Format an ISO timestamp as relative time (e.g., "2 hours ago").
    
    Args:
        iso_timestamp: ISO format timestamp string
        
    Returns:
        Human-readable relative time string
    """
    try:
        from datetime import datetime
        
        # Parse ISO timestamp
        ts = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now()
        delta = now - ts
        
        # Calculate time units
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            weeks = int(seconds // 604800)
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    except (ValueError, AttributeError):
        return iso_timestamp[:10] if iso_timestamp else "Unknown"
