"""
Supabase Helper - Manages connections and CRUD operations for Supabase database and storage
"""

import os
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
from backend.config import get_config
from backend.utils.logger import get_section_logger

logger = get_section_logger('supabase')

# Module-level client cache
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Retrieve and cache the Supabase Client instance"""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    config = get_config()()
    url = config.SUPABASE_URL
    # Ensure url has https:// prefix
    if url and not url.startswith('http'):
        url = f"https://{url}"

    # Prefer Service Role Key for backend administration (e.g. bypass RLS / write to storage)
    key = config.SUPABASE_SERVICE_KEY or config.SUPABASE_ANON_KEY

    if not url or not key:
        logger.warning("Supabase URL or Key not set. Cloud integrations are inactive.")
        return None

    try:
        _supabase_client = create_client(url, key)
        logger.info(f"Supabase client initialized successfully targeting project: {url}")
        return _supabase_client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {str(e)}")
        return None


def is_supabase_active() -> bool:
    """Helper to check if Supabase is configured and active"""
    return get_supabase_client() is not None


# ─── DATABASE OPERATIONS ──────────────────────────────────────────────────────

def supabase_insert(table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a single row into a Supabase table"""
    client = get_supabase_client()
    if not client:
        return None
    try:
        response = client.table(table).insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Supabase Insert error in table '{table}': {str(e)}")
        return None


def supabase_update(table: str, row_id: int, data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Update row(s) in a Supabase table by ID"""
    client = get_supabase_client()
    if not client:
        return None
    try:
        response = client.table(table).update(data).eq('id', row_id).execute()
        return response.data
    except Exception as e:
        logger.error(f"Supabase Update error in table '{table}' for ID {row_id}: {str(e)}")
        return None


def supabase_select(table: str, select_str: str = "*", filters: Dict[str, Any] = None, limit: int = 1000) -> List[Dict[str, Any]]:
    """Select rows from a Supabase table with optional exact matches"""
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = client.table(table).select(select_str)
        if filters:
            for k, v in filters.items():
                query = query.eq(k, v)
        response = query.limit(limit).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Supabase Select error in table '{table}': {str(e)}")
        return []


# ─── STORAGE OPERATIONS ────────────────────────────────────────────────────────

def supabase_upload_file(bucket: str, path: str, file_content: bytes, content_type: str = "text/plain") -> bool:
    """Upload or overwrite a file in a Supabase Storage bucket"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Check if file exists to decide whether to upload or update
        # (PostgREST storage API throws error if file exists on standard upload)
        try:
            # Attempt to update first (overwrite)
            client.storage.from_(bucket).upload(
                path=path,
                file=file_content,
                file_options={"content-type": content_type, "x-upsert": "true"}
            )
        except Exception:
            # Fallback to update directly if standard upsert flags fail
            client.storage.from_(bucket).update(
                path=path,
                file=file_content,
                file_options={"content-type": content_type}
            )
        return True
    except Exception as e:
        logger.error(f"Supabase Storage Upload failed for '{bucket}/{path}': {str(e)}")
        return False


def supabase_download_file(bucket: str, path: str) -> Optional[bytes]:
    """Retrieve file bytes from a Supabase Storage bucket"""
    client = get_supabase_client()
    if not client:
        return None
    try:
        response = client.storage.from_(bucket).download(path)
        return response
    except Exception as e:
        logger.debug(f"Supabase Storage Download failed for '{bucket}/{path}': {str(e)}")
        return None


def supabase_list_files(bucket: str, path: str = "") -> List[Dict[str, Any]]:
    """List assets inside a Supabase Storage bucket subfolder"""
    client = get_supabase_client()
    if not client:
        return []
    try:
        response = client.storage.from_(bucket).list(path)
        return response or []
    except Exception as e:
        logger.error(f"Supabase Storage List failed for '{bucket}/{path}': {str(e)}")
        return []


def supabase_delete_file(bucket: str, path: str) -> bool:
    """Remove a file from a Supabase Storage bucket"""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.storage.from_(bucket).remove([path])
        return True
    except Exception as e:
        logger.error(f"Supabase Storage Delete failed for '{bucket}/{path}': {str(e)}")
        return False
