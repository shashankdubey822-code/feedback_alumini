"""
Admin Routes - Handle authentication and data management
"""

from flask import Blueprint, request, jsonify, current_app
import os
import sqlite3
import pandas as pd
from datetime import datetime
from ..utils.logger import get_logger, log_endpoint_access

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Simple hardcoded password for now (could be an environment variable)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

@admin_bp.route('/login', methods=['POST'])
@log_endpoint_access
def login():
    """Admin login endpoint"""
    data = request.get_json()
    password = data.get('password')
    
    if password == ADMIN_PASSWORD:
        # In a real app, generate a proper JWT
        return jsonify({'success': True, 'token': 'mock-admin-token'}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid password'}), 401

@admin_bp.route('/upload_csv', methods=['POST'])
@log_endpoint_access
def upload_csv():
    """Handle CSV file upload and database insertion"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
            df = pd.read_csv(file)

            # Data cleaning and normalization
            # Convert roll_no to uppercase for consistency
            if 'roll_no' in df.columns:
                df['roll_no'] = df['roll_no'].astype(str).str.upper()
            if 'roll_no_original' in df.columns:
                df['roll_no_original'] = df['roll_no_original'].astype(str).str.upper()

            conn = sqlite3.connect(db_path)
            # Replace or append? For this use case, let's append but check for duplicates if possible
            df.to_sql('dashboard_data', conn, if_exists='append', index=False)
            conn.close()

            return jsonify({'success': True, 'message': f'Uploaded {len(df)} rows'}), 200
        except Exception as e:
            logger.error(f"Upload error: {str(e)}")
            return jsonify({'error': str(e)}), 500

@admin_bp.route('/fetch_google_link', methods=['POST'])
@log_endpoint_access
def fetch_google_link():
    """Fetch data from a public Google Sheets CSV export link"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        # Convert Google Sheets URL to CSV export URL if needed
        if 'docs.google.com/spreadsheets' in url and '/export' not in url:
            if '/edit' in url:
                url = url.split('/edit')[0] + '/export?format=csv'
            else:
                url = url.rstrip('/') + '/export?format=csv'

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        df = pd.read_csv(url)

        # Data cleaning and normalization
        # Convert roll_no to uppercase for consistency
        if 'roll_no' in df.columns:
            df['roll_no'] = df['roll_no'].astype(str).str.upper()
        if 'roll_no_original' in df.columns:
            df['roll_no_original'] = df['roll_no_original'].astype(str).str.upper()

        conn = sqlite3.connect(db_path)
        df.to_sql('dashboard_data', conn, if_exists='append', index=False)
        conn.close()

        return jsonify({'success': True, 'message': f'Fetched {len(df)} rows from Google Sheets'}), 200
    except Exception as e:
        logger.error(f"Google fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/events', methods=['GET'])
def get_events():
    """Get list of feedback events (stub)"""
    return jsonify({'success': True, 'events': []}), 200

@admin_bp.route('/generate_form', methods=['POST'])
def generate_form():
    """Generate a Google Form (stub)"""
    return jsonify({'success': True, 'form_url': 'https://forms.google.com/test'}), 200
