from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {"request": request, "active_page": "dashboard"},
    )


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ── Data ──────────────────────────────────────────────────────────────────
@router.get("/data/query", response_class=HTMLResponse, include_in_schema=False)
async def query_page(request: Request):
    return templates.TemplateResponse("pages/query.html",
        {"request": request, "active_page": "query"})


@router.get("/data/datasets", response_class=HTMLResponse, include_in_schema=False)
async def datasets_page(request: Request):
    return templates.TemplateResponse("pages/datasets.html",
        {"request": request, "active_page": "datasets"})


# ── Analysis ──────────────────────────────────────────────────────────────
@router.get("/aiml/jupyter", response_class=HTMLResponse, include_in_schema=False)
async def jupyter_page(request: Request):
    return templates.TemplateResponse("pages/jupyter.html",
        {"request": request, "active_page": "jupyter"})


# ── Models ────────────────────────────────────────────────────────────────
@router.get("/aiml/mlflow", response_class=HTMLResponse, include_in_schema=False)
async def mlflow_page(request: Request):
    return templates.TemplateResponse("pages/mlflow.html",
        {"request": request, "active_page": "mlflow"})


# ── Notice ────────────────────────────────────────────────────────────────
@router.get("/board", response_class=HTMLResponse, include_in_schema=False)
async def board_page(request: Request):
    return templates.TemplateResponse("pages/board.html",
        {"request": request, "active_page": "board"})


# ── Files (S3 스토리지) ────────────────────────────────────────────────────
@router.get("/files", response_class=HTMLResponse, include_in_schema=False)
async def files_page(request: Request):
    from app.core.config import get_settings
    s3_bucket = get_settings().s3_bucket_name
    return templates.TemplateResponse("pages/files.html",
        {"request": request, "active_page": "files", "s3_bucket": s3_bucket})


# ── Inference Test ────────────────────────────────────────────────────────
@router.get("/aiml/inference", response_class=HTMLResponse, include_in_schema=False)
async def inference_page(request: Request):
    from app.core.config import get_settings
    settings = get_settings()
    return templates.TemplateResponse("pages/inference.html",
        {"request": request, "active_page": "inference",
         "inference_url": settings.inference_base_url,
         "inference_host": settings.inference_default_host})


# ── Airflow ───────────────────────────────────────────────────────────────
@router.get("/airflow", response_class=HTMLResponse, include_in_schema=False)
async def airflow_page(request: Request):
    return templates.TemplateResponse("pages/airflow.html",
        {"request": request, "active_page": "airflow"})


# ── Admin ─────────────────────────────────────────────────────────────────
@router.get("/admin/users", response_class=HTMLResponse, include_in_schema=False)
async def admin_users_page(request: Request):
    return templates.TemplateResponse("pages/admin_users.html",
        {"request": request, "active_page": "admin-users"})


@router.get("/admin/settings", response_class=HTMLResponse, include_in_schema=False)
async def admin_settings_page(request: Request):
    return templates.TemplateResponse("pages/admin_settings.html",
        {"request": request, "active_page": "admin-settings"})
