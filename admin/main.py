from fastapi import Depends

# Import the module (not only the FastAPI object) so Retrieval v2 can replace the
# production context builder before the first request is served.
from admin import app as app_module
from admin.retrieval_v2_runtime import install as install_retrieval_v2
from admin.support_api import router as support_router
from admin.cases_api import router as cases_router

install_retrieval_v2(app_module)
app = app_module.app
require_auth = app_module.require_auth

app.include_router(cases_router, dependencies=[Depends(require_auth)])
app.include_router(support_router)
