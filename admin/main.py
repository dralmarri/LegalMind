from fastapi import Depends

# Import the module (not only the FastAPI object) so runtime installers can patch
# production dependencies before the first request is served.
from admin import app as app_module
from admin import llm as llm_module
from admin.llm_resilience import install as install_llm_resilience
from admin.retrieval_v2_runtime import install as install_retrieval_v2
from admin.support_api import router as support_router
from admin.cases_api import router as cases_router

# Long source-grounded legal drafts may legitimately exceed ordinary SDK read
# windows.  Harden provider transport without shrinking Retrieval v2 context.
install_llm_resilience(llm_module)
install_retrieval_v2(app_module)
app = app_module.app
require_auth = app_module.require_auth

app.include_router(cases_router, dependencies=[Depends(require_auth)])
app.include_router(support_router, dependencies=[Depends(require_auth)])
