# GamiServer API Server

A Flask-based API server that manages game repositories, packages them into tar.xz archives, and provides a web UI for management.

## Features

- **Repository Management**: Add, remove, and list GitHub repositories
- **Search Functionality**: Search repositories by name or URL
- **Package Generation**: Automatically packages repositories into tar.xz format when requested
- **Web UI**: Beautiful, responsive web interface for managing games
- **Release Integration**: Fetches and displays releases from the main GamiServer repository
- **RESTful API**: Complete API for programmatic access
- **Database**: SQLite for persistent storage
- **Health Checks**: Built-in health monitoring endpoints

## Setup & Installation

### Prerequisites
- Python 3.8+
- Git
- tar and xz-utils (usually pre-installed on Linux/macOS)

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Minecatl1/GamiServer.git
   cd GamiServer
   git checkout api-server
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up GitHub token (optional but recommended)**:
   ```bash
   export GITHUB_TOKEN=your_github_token_here
   ```

5. **Run the server**:
   ```bash
   python app.py
   ```

   The server will start on `http://localhost:5000`

## API Endpoints

### Get Repositories
```
GET /api/repos
```
Returns all repositories in the database.

**Response:**
```json
[
  {
    "id": 1,
    "url": "https://github.com/owner/repo",
    "name": "repo",
    "added_at": "2026-06-08T01:40:12Z"
  }
]
```

### Add Repository
```
POST /api/repos
Content-Type: application/json

{
  "url": "https://github.com/owner/repo"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Repository added successfully"
}
```

### Remove Repository
```
DELETE /api/repos/<id>
```

### Search Repositories
```
GET /api/search?q=query
```
Search by repository name or URL.

### Download Game Package
```
GET /api/game/<game_id>
```
Fetches a repository, packages it as tar.xz, and returns the file.

### Get Latest Releases
```
GET /api/releases
```
Fetches releases from the main GamiServer repository.

### Health Check
```
GET /health
```
Returns server health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-06-08T01:40:12.123456Z"
}
```

## Web UI Usage

1. Navigate to `http://localhost:5000` in your browser
2. **Add Repository**: Enter a GitHub repository URL and click "Add Repository"
3. **View List**: See all repositories in the "Repository List" section
4. **Search**: Use the search bar to find repositories quickly
5. **Download**: Click "Download" to get a tar.xz package of any repository
6. **Remove**: Click "Remove" to delete a repository from the list
7. **View Releases**: See the latest releases in the "Latest Releases" section

## Directory Structure

```
.
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── templates/
│   └── index.html             # Web UI
├── .github/workflows/
│   └── deploy-server.yml      # GitHub Actions deployment workflow
├── gami_server.db             # SQLite database (auto-generated)
└── README-API.md              # This file
```

## Database Schema

### repos table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| url | TEXT | GitHub repository URL (unique) |
| name | TEXT | Repository name |
| added_at | TIMESTAMP | When the repository was added |

## GitHub Actions Workflow

The `.github/workflows/deploy-server.yml` workflow:
- Runs on push to `api-server` branch and manual trigger
- Tests Python syntax and imports
- Initializes the database
- Starts the server and tests API endpoints
- Uploads server logs for debugging

## Notes

- Large repositories may take time to clone and package
- Packages are generated on-demand during the request
- The `GITHUB_TOKEN` environment variable improves API rate limits
- Database file (`gami_server.db`) persists between runs
- All sensitive data should be passed via environment variables

## Troubleshooting

### Port already in use
If port 5000 is already in use, modify the port in `app.py`:
```python
app.run(debug=False, host='0.0.0.0', port=YOUR_PORT)
```

### Git clone failures
Ensure your system has git installed and GitHub token (if using private repos):
```bash
export GITHUB_TOKEN=your_token
```

### Database errors
Delete `gami_server.db` to reset the database:
```bash
rm gami_server.db
python app.py
```

## Contributing

1. Create a feature branch from `api-server`
2. Make your changes
3. Test locally with `python app.py`
4. Push and create a pull request

## License

See main repository for license information.
