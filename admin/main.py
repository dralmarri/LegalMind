from admin.app import app, require_auth
from admin.cases_api import configure_case_router

app.include_router(configure_case_router(require_auth))
