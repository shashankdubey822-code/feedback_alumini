"""
insforge_helper.py — HTTP REST connection for InsForge Storage.

Replaces legacy helper for file storage.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

def is_insforge_active() -> bool:
    """Check if InsForge API keys are present."""
    base_url = os.environ.get('INSFORGE_API_BASE_URL', '').strip()
    api_key = os.environ.get('INSFORGE_API_KEY', '').strip()
    return bool(base_url and api_key)

def _get_headers():
    api_key = os.environ.get('INSFORGE_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError("INSFORGE_API_KEY environment variable is not set")
    return {
        "Authorization": f"Bearer {api_key}"
    }

def _get_base_url():
    base_url = os.environ.get('INSFORGE_API_BASE_URL', '').strip()
    if not base_url:
        raise RuntimeError("INSFORGE_API_BASE_URL environment variable is not set")
    return base_url.rstrip('/')

def insforge_upload_file(bucket: str, path: str, file_bytes: bytes, mime_type: str = "application/octet-stream") -> bool:
    """Upload a file to InsForge storage."""
    try:
        url = f"{_get_base_url()}/api/storage/buckets/{bucket}/objects/{path}"
        headers = _get_headers()
        
        # We use the deprecated direct PUT for simplicity
        files = {
            'file': (os.path.basename(path), file_bytes, mime_type)
        }
        
        resp = requests.put(url, headers=headers, files=files)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error uploading file to InsForge ({bucket}/{path}): {e}")
        return False

def insforge_download_file(bucket: str, path: str) -> bytes | None:
    """Download a file from InsForge storage."""
    try:
        # Get strategy
        strategy_url = f"{_get_base_url()}/api/storage/buckets/{bucket}/download-strategy/objects/{path}"
        headers = _get_headers()
        
        resp = requests.get(strategy_url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        strategy = resp.json()
        
        download_url = strategy.get('url')
        if not download_url:
            # Fallback to direct URL if strategy fails to provide it
            download_url = f"{_get_base_url()}/api/storage/buckets/{bucket}/objects/{path}"
        elif download_url.startswith('/'):
            download_url = _get_base_url() + download_url
            
        file_resp = requests.get(download_url, headers=headers)
        if file_resp.status_code == 404:
            return None
        file_resp.raise_for_status()
        return file_resp.content
    except Exception as e:
        logger.error(f"Error downloading file from InsForge ({bucket}/{path}): {e}")
        return None

def insforge_list_files(bucket: str, prefix: str = "") -> list:
    """List files in an InsForge storage bucket."""
    try:
        url = f"{_get_base_url()}/api/storage/buckets/{bucket}/objects"
        headers = _get_headers()
        params = {}
        if prefix:
            params['prefix'] = prefix
            
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get('data', [])
    except Exception as e:
        logger.error(f"Error listing files in InsForge ({bucket}, prefix={prefix}): {e}")
        return []

def insforge_delete_file(bucket: str, path: str) -> bool:
    """Delete a file from InsForge storage."""
    try:
        url = f"{_get_base_url()}/api/storage/buckets/{bucket}/objects/{path}"
        headers = _get_headers()
        
        resp = requests.delete(url, headers=headers)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error deleting file from InsForge ({bucket}/{path}): {e}")
        return False
