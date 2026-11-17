# backend/app/main_clean.py
# This file was a verbatim duplicate of main.py. It now re-exports the app so
# security settings (CORS, docs, headers) are maintained in one place.
from .main import app  # noqa: F401
