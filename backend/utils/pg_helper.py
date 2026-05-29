import os
import psycopg2
import psycopg2.extras
import re
import logging
from urllib.parse import urlparse

# Make exceptions accessible from the module just like sqlite3
IntegrityError = psycopg2.IntegrityError
OperationalError = psycopg2.OperationalError
Error = psycopg2.Error

class Row(psycopg2.extras.DictRow):
    pass

class CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        
    def execute(self, query, params=None):
        original_query = query
        # Very simple replacement of ? to %s for PostgreSQL
        # We assume ? is not used inside string literals in our simple queries
        query = query.replace('?', '%s')
        
        # Translate date functions
        query = query.replace('strftime("%Y-%m", timestamp_normalized)', "TO_CHAR(CAST(timestamp_normalized AS TIMESTAMP), 'YYYY-MM')")
        query = query.replace("strftime('%Y-%m', timestamp_normalized)", "TO_CHAR(CAST(timestamp_normalized AS TIMESTAMP), 'YYYY-MM')")
        
        # Translate SQLite-specific table information checks into Postgres
        if "PRAGMA table_info" in query:
            match = re.search(r'PRAGMA table_info\((.*?)\)', query)
            if match:
                table = match.group(1).strip()
                query = f"SELECT column_name as name, data_type as type FROM information_schema.columns WHERE table_name = '{table}'"
        elif "PRAGMA" in query:
            # We ignore other pragmas like journal_mode or busy_timeout
            return self
            
        # Translate AUTOINCREMENT -> SERIAL
        query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
        try:
            if params:
                self._cursor.execute(query, params)
            else:
                self._cursor.execute(query)
        except Exception as e:
            logging.error(f"Error executing query: {query}\nParams: {params}\nError: {str(e)}")
            raise
        return self

    def fetchone(self):
        return self._cursor.fetchone()
        
    def fetchall(self):
        return self._cursor.fetchall()
        
    def fetchmany(self, size=None):
        if size is None:
            return self._cursor.fetchmany()
        return self._cursor.fetchmany(size)
        
    @property
    def rowcount(self):
        return self._cursor.rowcount
        
    @property
    def lastrowid(self):
        # In postgres, we'd normally use RETURNING id. We can try to approximate if needed,
        # but for simplicity we return None or try to fetch the last inserted ID.
        try:
            self._cursor.execute("SELECT lastval()")
            res = self._cursor.fetchone()
            if res:
                return res[0]
        except:
            self._cursor.connection.rollback()
        return None
        
    def close(self):
        self._cursor.close()

class ConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None
        
    def cursor(self):
        if self.row_factory is not None:
            # If row_factory is set, use DictCursor to mimic sqlite3.Row
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cur = self._conn.cursor()
        return CursorWrapper(cur)
        
    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)
        
    def commit(self):
        self._conn.commit()
        
    def rollback(self):
        self._conn.rollback()
        
    def close(self):
        self._conn.close()

def connect(database, timeout=None, check_same_thread=None):
    """
    Acts as a drop-in replacement for sqlite3.connect().
    Instead of connecting to a local file, connects to DATABASE_URL.
    """
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    conn = psycopg2.connect(db_url)
    return ConnectionWrapper(conn)
