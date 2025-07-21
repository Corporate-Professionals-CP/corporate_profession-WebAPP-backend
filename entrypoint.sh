#!/bin/bash
echo "Running Server"
alembic upgrade head
exec gunicorn --bind 0.0.0.0:$PORT app.main:app --timeout 0 -w 3 -k uvicorn.workers.UvicornWorker
