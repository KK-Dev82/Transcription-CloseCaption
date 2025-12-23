"""
API Endpoints สำหรับดู Logs
รองรับการดู API logs, Worker logs, และ System logs
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Log file paths
LOG_PATHS = {
    "api": "/tmp/main-api.log",
    "gpu0": "/tmp/rq-worker-gpu0.log",
    "gpu1": "/tmp/rq-worker-gpu1.log",
    "cpu0": "/tmp/rq-worker-cpu-0.log",
    "cpu1": "/tmp/rq-worker-cpu-1.log",
    "preprocess0": "/tmp/rq-worker-preprocess-0.log",
    "preprocess1": "/tmp/rq-worker-preprocess-1.log",
    "preprocess2": "/tmp/rq-worker-preprocess-2.log",
    "preprocess3": "/tmp/rq-worker-preprocess-3.log",
    "preprocess4": "/tmp/rq-worker-preprocess-4.log",
    "preprocess5": "/tmp/rq-worker-preprocess-5.log",
    "whisper": "/tmp/whisper.log",
    "video-worker": "/tmp/video-worker.log",
}

@router.get("/")
async def list_logs():
    """List available log files"""
    available_logs = []
    for name, path in LOG_PATHS.items():
        log_path = Path(path)
        if log_path.exists():
            stat = log_path.stat()
            available_logs.append({
                "name": name,
                "path": path,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "lines": sum(1 for _ in open(path, 'rb')) if stat.st_size > 0 else 0
            })
    
    return {
        "available_logs": sorted(available_logs, key=lambda x: x["name"]),
        "count": len(available_logs),
        "timestamp": datetime.now().isoformat()
    }

@router.get("/{log_name}")
async def get_log(
    log_name: str,
    lines: int = Query(100, ge=1, le=10000, description="Number of lines to retrieve"),
    tail: bool = Query(True, description="Get tail (last N lines) or head (first N lines)"),
    filter: Optional[str] = Query(None, description="Filter lines containing this text (case-insensitive)")
):
    """
    Get log file contents
    
    Args:
        log_name: Log file name (api, gpu0, gpu1, cpu0, cpu1, preprocess0-5, whisper, video-worker)
        lines: Number of lines to retrieve (1-10000)
        tail: If True, get last N lines; if False, get first N lines
        filter: Optional filter to search for specific text
    """
    if log_name not in LOG_PATHS:
        raise HTTPException(
            status_code=404,
            detail=f"Log '{log_name}' not found. Available logs: {', '.join(LOG_PATHS.keys())}"
        )
    
    log_path = Path(LOG_PATHS[log_name])
    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found: {log_path}"
        )
    
    try:
        # Read log file
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Apply filter if provided
        if filter:
            all_lines = [line for line in all_lines if filter.lower() in line.lower()]
        
        # Get requested lines
        if tail:
            if len(all_lines) > lines:
                log_lines = all_lines[-lines:]
            else:
                log_lines = all_lines
        else:
            log_lines = all_lines[:lines]
        
        # Get file stats
        stat = log_path.stat()
        
        return {
            "log_name": log_name,
            "log_path": str(log_path),
            "total_lines": len(all_lines),
            "filtered_lines": len(all_lines) if filter else None,
            "returned_lines": len(log_lines),
            "lines": log_lines,
            "file_size": stat.st_size,
            "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "filter": filter,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error reading log {log_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reading log: {str(e)}"
        )

@router.get("/{log_name}/search")
async def search_log(
    log_name: str,
    query: str = Query(..., description="Search query (case-insensitive)"),
    lines: int = Query(50, ge=1, le=1000, description="Number of matching lines to return"),
    context: int = Query(2, ge=0, le=5, description="Number of context lines before/after match")
):
    """
    Search log file for specific text
    
    Args:
        log_name: Log file name
        query: Search query
        lines: Maximum number of matches to return
        context: Number of context lines before/after each match
    """
    if log_name not in LOG_PATHS:
        raise HTTPException(
            status_code=404,
            detail=f"Log '{log_name}' not found. Available logs: {', '.join(LOG_PATHS.keys())}"
        )
    
    log_path = Path(LOG_PATHS[log_name])
    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found: {log_path}"
        )
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        matches = []
        query_lower = query.lower()
        
        for i, line in enumerate(all_lines):
            if query_lower in line.lower():
                # Get context lines
                start = max(0, i - context)
                end = min(len(all_lines), i + context + 1)
                context_lines = all_lines[start:end]
                
                matches.append({
                    "line_number": i + 1,
                    "match_line": line.rstrip(),
                    "context": [l.rstrip() for l in context_lines],
                    "context_start": start + 1,
                    "context_end": end
                })
                
                if len(matches) >= lines:
                    break
        
        return {
            "log_name": log_name,
            "query": query,
            "total_matches": len(matches),
            "matches": matches,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching log {log_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching log: {str(e)}"
        )

@router.get("/{log_name}/stats")
async def get_log_stats(log_name: str):
    """Get statistics about a log file"""
    if log_name not in LOG_PATHS:
        raise HTTPException(
            status_code=404,
            detail=f"Log '{log_name}' not found"
        )
    
    log_path = Path(LOG_PATHS[log_name])
    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found: {log_path}"
        )
    
    try:
        stat = log_path.stat()
        
        # Count lines and analyze content
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Count error/warning/info
        error_count = sum(1 for line in all_lines if 'error' in line.lower() or '❌' in line)
        warning_count = sum(1 for line in all_lines if 'warning' in line.lower() or '⚠️' in line)
        info_count = sum(1 for line in all_lines if 'info' in line.lower() or 'ℹ️' in line)
        success_count = sum(1 for line in all_lines if 'success' in line.lower() or '✅' in line)
        
        return {
            "log_name": log_name,
            "log_path": str(log_path),
            "file_size": stat.st_size,
            "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
            "total_lines": len(all_lines),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "stats": {
                "errors": error_count,
                "warnings": warning_count,
                "info": info_count,
                "success": success_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting log stats {log_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting log stats: {str(e)}"
        )

@router.get("/all/recent")
async def get_recent_logs(
    lines: int = Query(20, ge=1, le=100, description="Number of lines per log"),
    log_names: Optional[str] = Query(None, description="Comma-separated list of log names (default: all)")
):
    """
    Get recent lines from multiple logs at once
    
    Args:
        lines: Number of lines per log
        log_names: Comma-separated list of log names (e.g., "api,gpu0,gpu1")
    """
    if log_names:
        requested_logs = [name.strip() for name in log_names.split(",")]
    else:
        requested_logs = list(LOG_PATHS.keys())
    
    results = {}
    for log_name in requested_logs:
        if log_name in LOG_PATHS:
            log_path = Path(LOG_PATHS[log_name])
            if log_path.exists():
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        all_lines = f.readlines()
                    
                    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    results[log_name] = {
                        "lines": [l.rstrip() for l in recent_lines],
                        "total_lines": len(all_lines),
                        "returned_lines": len(recent_lines)
                    }
                except Exception as e:
                    results[log_name] = {"error": str(e)}
            else:
                results[log_name] = {"error": "File not found"}
        else:
            results[log_name] = {"error": "Log name not found"}
    
    return {
        "logs": results,
        "timestamp": datetime.now().isoformat()
    }

