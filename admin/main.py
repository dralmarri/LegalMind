from fastapi import Depends

from admin.app import app, require_auth
from admin.cases_api import router as cases_router

app.include_router(cases_router, dependencies=[Depends(require_auth)])
