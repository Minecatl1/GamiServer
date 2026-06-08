from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import os
import requests
import tarfile
import io
from datetime import datetime
import json
import subprocess
import shutil
import logging

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE = 'gami_server.db'
MAIN_REPO = 'Minecatl1/GamiServer'
GITHUB_API = 'https://api.github.com'

def get_tunnel_url():
    """Get Cloudflare Tunnel URL from environment or try to extract from logs"""
    tunnel_url = os.environ.get('CLOUDFLARE_TUNNEL_URL')
    if tunnel_url:
        return tunnel_url
    
    # Try to read from cloudflared logs if running in Docker
    try:
        result = subprocess.run(['curl', '-s', 'http://127.0.0.1:40025/metrics'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Parse metrics to find tunnel URL
            for line in result.stdout.split('\n'):
                if 'tunnel_url' in line or 'url' in line:
                    logger.info(f"Tunnel metrics: {line}")
    except:
        pass
    
    return None

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS repos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Serve the web UI"""
    return render_template('index.html')

@app.route('/api/repos', methods=['GET'])
def get_repos():
    """Get all repositories in the list"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM repos ORDER BY added_at DESC')
    repos = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(repos)

@app.route('/api/repos', methods=['POST'])
def add_repo():
    """Add a new repository to the list"""
    data = request.json
    repo_url = data.get('url', '').strip()
    
    if not repo_url:
        return jsonify({'error': 'Repository URL is required'}), 400
    
    # Validate GitHub URL
    if 'github.com' not in repo_url:
        return jsonify({'error': 'Must be a valid GitHub repository URL'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO repos (url, name) VALUES (?, ?)', 
                 (repo_url, repo_url.split('/')[-1].replace('.git', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Repository added successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Repository already in list'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/repos/<int:repo_id>', methods=['DELETE'])
def remove_repo(repo_id):
    """Remove a repository from the list"""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM repos WHERE id = ?', (repo_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/search', methods=['GET'])
def search_repos():
    """Search repositories by name or URL"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM repos WHERE url LIKE ? OR name LIKE ? ORDER BY added_at DESC',
             (f'%{query}%', f'%{query}%'))
    repos = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(repos)

@app.route('/api/game/<game_id>')
def get_game_package(game_id):
    """
    Fetch a game repository, package it, and return the tar.xz file
    """
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM repos WHERE name = ? OR id = ?', (game_id, game_id))
        repo = c.fetchone()
        conn.close()
        
        if not repo:
            return jsonify({'error': f'Game "{game_id}" not found in list'}), 404
        
        repo_url = repo['url']
        repo_name = repo['name']
        
        # Clone the repository
        temp_dir = f'/tmp/{repo_name}_{datetime.now().timestamp()}'
        os.makedirs(temp_dir, exist_ok=True)
        
        clone_path = os.path.join(temp_dir, repo_name)
        result = subprocess.run(['git', 'clone', repo_url, clone_path], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'error': f'Failed to clone repository: {repo_url}'}), 500
        
        # Create tar.xz package
        package_path = os.path.join(temp_dir, f'{repo_name}.tar.xz')
        with tarfile.open(package_path, 'w:xz') as tar:
            tar.add(clone_path, arcname=repo_name)
        
        # Read the package file
        with open(package_path, 'rb') as f:
            package_data = f.read()
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        return send_file(
            io.BytesIO(package_data),
            mimetype='application/x-xz',
            as_attachment=True,
            download_name=f'{repo_name}.tar.xz'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases')
def get_releases():
    """Fetch releases from the main GamiServer repository"""
    try:
        headers = {}
        if 'GITHUB_TOKEN' in os.environ:
            headers['Authorization'] = f'token {os.environ["GITHUB_TOKEN"]}'
        
        response = requests.get(
            f'{GITHUB_API}/repos/{MAIN_REPO}/releases',
            headers=headers
        )
        response.raise_for_status()
        releases = response.json()
        
        return jsonify(releases)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'tunnel_url': get_tunnel_url()
    })

@app.route('/api/info')
def info():
    """Get server information including tunnel URL"""
    tunnel_url = get_tunnel_url()
    if not tunnel_url:
        tunnel_url = os.environ.get('CLOUDFLARE_TUNNEL_URL', 'Tunnel URL not available')
    
    return jsonify({
        'server': 'GamiServer API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'tunnel_url': tunnel_url,
        'tunnel_available': tunnel_url != 'Tunnel URL not available'
    })

if __name__ == '__main__':
    init_db()
    logger.info("GamiServer API starting...")
    
    # Log tunnel URL if available
    tunnel_url = get_tunnel_url()
    if tunnel_url:
        logger.info(f"✓ Cloudflare Tunnel available at: {tunnel_url}")
    else:
        logger.info("⚠ Cloudflare Tunnel not detected")
    
    app.run(debug=False, host='0.0.0.0', port=5000)
