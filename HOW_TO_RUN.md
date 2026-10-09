# How to Run CampusEats

This project has a FastAPI backend, a static HTML/CSS/JavaScript frontend, and a PostgreSQL database. No Node.js installation is required for the frontend.

## Requirements

- Python 3.12 recommended.
- PostgreSQL 16, running locally or at a reachable database host.
- The CampusEats database and tables initialized from the course database setup.
- A terminal with `curl` for the optional API checks.

The repository does not currently include a root-level `schema.sql`; its `docker-compose.yml` refers to that missing file. Prepare the database using the course-provided database setup before starting the API.

## 1. Open the project directory

```sh
cd /path/to/campusEats
```

Replace `/path/to/campusEats` with the directory where you cloned or extracted the project.

## 2. Create and activate a Python virtual environment

Linux or macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install the Python dependencies

With the virtual environment activated:

```sh
python -m pip install --upgrade pip
python -m pip install -r dependency_technology.txt
```

The dependency list contains FastAPI, Uvicorn, Psycopg (PostgreSQL driver), Pydantic Settings, Passlib with bcrypt, and python-dotenv.

## 4. Configure PostgreSQL

Create a `.env` file in the project root, or export `DATABASE_URL` in the terminal. Use the actual username, password, host, port, and database configured for your PostgreSQL instance:

```dotenv
DATABASE_URL=postgresql://<username>:<password>@localhost:5432/<database>
```

Replace the angle-bracketed placeholders; do not include the brackets. Keep real credentials private and do not commit `.env`.

Before starting the API, make sure PostgreSQL is running and the CampusEats schema/tables have been initialized. The API does not create the database schema automatically.

## 5. Start the API

In the project root, with the virtual environment active:

```sh
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Leave this terminal open while using the application. Verify the API and database from another terminal:

```sh
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/health/database
```

The interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## 6. Start the frontend

Open a second terminal. From the project root, run a static file server on port 5500:

```sh
cd interface
python -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/> in a browser. The frontend uses the API at port 8000 by default; the API's default CORS configuration allows this frontend origin.

## Stop the application

Press `Ctrl+C` in each terminal running Uvicorn or the static file server. Deactivate the virtual environment when finished:

```sh
deactivate
```

## Troubleshooting

- **Cannot reach the API:** confirm the API terminal says Uvicorn is listening on port 8000 and that `/health` responds.
- **Database connection error:** verify PostgreSQL is running, `DATABASE_URL` is correct, and the CampusEats database/schema has been provisioned.
- **Frontend request blocked:** serve the files from `http://127.0.0.1:5500` or `http://localhost:5500`; opening the HTML directly as a `file://` URL does not provide the configured web origin.
- **Missing Python package:** activate `.venv` and rerun `python -m pip install -r dependency_technology.txt`.
