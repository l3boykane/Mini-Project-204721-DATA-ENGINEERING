# backend/app/main.py
from __future__ import annotations
import os, uuid, traceback, logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import User, Dataset, StatRecord, RainPoint
from .schemas import UserOut, RegisterIn, LoginIn, DatasetOut, StatRecordOut
from .auth import (
    hash_password, verify_password,
    create_access_token, set_auth_cookie, clear_auth_cookie,
    get_current_user
)
from .utils import (
    summarize_table,
    ingest_nc_north_adm2_to_db
)
# Base.metadata.create_all(bind=engine)
# ---------------- App & CORS ----------------
app = FastAPI(title="Landslide Ingest API", version="1.0.0")

FRONTEND_ORIGIN = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

# ---------------- Settings ----------------
STORAGE_DIR = os.getenv("STORAGE_DIR", "/data/storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

PROV_BOUNDARY = os.getenv(
    "PROVINCE_BOUNDARY_PATH",
    os.path.join(STORAGE_DIR, "admin/gadm41_THA_2.shp")
)
NC_VAR_NAME = os.getenv("NC_VAR_NAME", "precip")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "4096"))
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024


# ---------------- Middleware (optional debug) ----------------
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info("REQ %s %s", request.method, request.url.path)
    resp = await call_next(request)
    logger.info("RES %s %s -> %s", request.method, request.url.path, resp.status_code)
    return resp


# ---------------- Auth Endpoints (เหมือนของเดิม) ----------------
@app.post("/auth/register", response_model=UserOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already registered")
    user = User(username=data.username, display_name=data.display_name, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid Username or password")
    token = create_access_token(sub=user.username, extra={"uid": user.id})
    set_auth_cookie(response, token)
    return user

@app.post("/auth/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}

@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------------- Upload NetCDF -> Ingest to Postgres (ใหม่) ----------------
@app.post("/upload")
async def upload_netcdf(
    file: UploadFile = File(...),
    note: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (file.filename.endswith(".nc") or file.content_type in {"application/x-netcdf","application/netcdf"}):
        raise HTTPException(400, "Please upload a .nc file")
    if not os.path.exists(PROV_BOUNDARY):
        raise HTTPException(400, f"Province boundary file not found: {PROV_BOUNDARY}")

    # 1) เก็บไฟล์ดิบชั่วคราว
    safe_name = f"{uuid.uuid4().hex}_RAW_{os.path.basename(file.filename)}"
    raw_path = os.path.join(STORAGE_DIR, safe_name)

    written = 0
    with open(raw_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk: break
            written += len(chunk)
            if written > MAX_BYTES:
                f.close()
                try: os.remove(raw_path)
                except: pass
                raise HTTPException(413, f"File too large (> {MAX_UPLOAD_MB} MB)")
            f.write(chunk)

    # 2) สร้างระเบียน dataset (เก็บอ้างอิงไฟล์ต้นฉบับ)
    row = Dataset(
        filename=file.filename,
        storage_path=raw_path,
        size_bytes=written,
        content_type=file.content_type or "application/x-netcdf",
        note=note,
        owner_id=user.id,
    )
    db.add(row); db.commit(); db.refresh(row)

    # 3) Ingest ลง Postgres แบบ row-wise เฉพาะภาคเหนือ
    try:
        total = ingest_nc_north_adm2_to_db(
            engine=db.get_bind(),
            dataset_id=row.id,
            nc_path=raw_path,
            var_name=NC_VAR_NAME,
            adm2_shp_path=PROV_BOUNDARY,
            table_name="rain_points",
        )
    except Exception as e:
        logger.exception("ingest failed: %s", e)
        raise HTTPException(400, f"Ingest failed: {e}")

    return {"dataset_id": row.id, "rows_inserted": total}


# ---------------- Upload CSV/XLSX (สถิติ) ----------------
@app.post("/upload-stats", response_model=StatRecordOut)
async def upload_stats(
    file: UploadFile = File(...),
    note: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (file.filename.endswith((".csv", ".xlsx", ".xls"))):
        raise HTTPException(400, "Please upload .csv or .xlsx")

    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    dest_path = os.path.join(STORAGE_DIR, safe_name)

    size = 0
    with open(dest_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk: break
            size += len(chunk)
            f.write(chunk)

    try:
        meta = summarize_table(dest_path)  # สำหรับ preview/UI
    except Exception as e:
        try: os.remove(dest_path)
        except: pass
        traceback.print_exc()
        raise HTTPException(400, f"Failed to read table: {e}")

    rec = StatRecord(
        filename=file.filename,
        storage_path=dest_path,
        size_bytes=size,
        content_type=file.content_type or "text/csv",
        meta=meta,
        note=note,
        owner_id=user.id,
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


# ---------------- (ตัวอย่าง) รายการ datasets/stats ----------------
@app.get("/datasets")
def list_datasets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(RainPoint).limit(50).all()
    return rows

@app.get("/stats", response_model=list[StatRecordOut])
def list_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(StatRecord).filter(StatRecord.owner_id == user.id).order_by(StatRecord.id.desc()).all()
    return rows
