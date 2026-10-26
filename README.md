# ErrorInsight – Intelligent Error Analyzer

## Run
1. Extract the ZIP.
2. Open the `ErrorInsight_Colorful` folder in VS Code.
3. Open Terminal in that folder.
4. Run `pip install -r requirements.txt`
5. Run `python app.py`
6. Open `http://127.0.0.1:5000`

IMPORTANT: Do not double-click templates/index.html. Start Flask and open the localhost address.

## Features
Professional colorful dashboard, JSON upload, error categorization, frequency analysis,
severity distribution, recurring errors, causes, recommendations and recent logs.

## API
GET /api/demo
POST /api/analyze (multipart field: file)


## Database storage (added)
- The app automatically creates `error_insight.db` in the same folder as `app.py` when it starts.
- SQLite is built into Python, so no separate database server or extra package is required.
- When you upload an `errors.json` file, the analyzed error records are saved to the `error_logs` table.
- `GET /api/history` returns recently stored records (default 100; maximum 1000).
- `GET /api/health` checks the database and reports how many records are stored.
- Demo mode displays the sample dataset but does not insert duplicates into the database.
- Keep `error_insight.db` to retain saved records. Back it up with your project.

The database file is created after the first run; it is not included in the ZIP.
