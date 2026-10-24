# CS543 Web Services — Assignment 6

## Team cover page

- Team lead: 20251651026 - Anurag Panda
- Member 2: 20251651074 - Puspender
- Member 3: 20251651079 - Rohit
- Member 4: 20251651034 - Dinesh Kushwaha
- Member 5: 20251651095 - Taj Ansari

## Assignment

**Honest responses: status codes, errors & validation**

This submission extends the existing CampusEats FastAPI Orders service. It does not create a second service.

## Run locally

1. Start the existing PostgreSQL database and set `DATABASE_URL` as required by `api/db.py`.
2. From the project root, activate the Python environment and run:

   ```sh
   uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```

3. Check `http://localhost:8000/health/database`.
4. Run the focused tests with `PYTHONPATH=. pytest -q tests/test_assignment5_http.py tests/test_assignment6_orders.py`.
5. With the service running and `curl` available, regenerate the live transcript using:

   ```sh
   bash run_transcript.sh
   ```

   `TEST_USER_ID`, `TEST_LOCATION_ID`, and `TEST_ITEM_ID` may be set for another database fixture. The defaults refer to the development database used to capture the included transcript.

The database must contain an available menu item and a saved location belonging to the selected test user. The transcript script starts a second, intentionally database-disconnected API process for the 503 retry check and stops it when complete.

## Deliverables

- `api/`: existing CampusEats service source.
- `openapi.yaml`: Assignment 6 response contract.
- `NOTES.md`: required status, error, retry, and representation notes.
- `transcript.txt`: captured `curl -i` exchanges from the running service.
- `run_transcript.sh`: reproducible transcript generator.
