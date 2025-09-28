# backend/app/main.py
from __future__ import annotations
import os, uuid, logging, io
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, aliased
from datetime import date
import pandas as pd
from sqlalchemy import select, func, asc, desc, and_, or_
from .database import Base, engine, get_db
from .models import User, UploadRainPoint, RainPoint, Province, District, UploadRisk, RiskPoint, IncidentStatisticsPoint
from .schemas import UserOut, RegisterIn, LoginIn, ListPaginationOut, ListProvinceDistrictPaginationOut, RainPointOut, ProvinceOut, DistrictOut, ProvinceListOut, DistrictListOut, ProvinceDistrictPointOut, RiskPointOut, ListRiskPaginationOut, IncidentStatisticsPointOut, ListIncidentStatisticsPaginationOut
from .auth import (
    hash_password, verify_password,
    create_access_token, set_auth_cookie, clear_auth_cookie,
    get_current_user
)
from .utils import (
    init_data,
    ingest_nc_north_adm2_to_db,
    ingest_dbf_to_db,
    ingest_excel_to_db
)
Base.metadata.create_all(bind=engine)
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
    os.path.join(STORAGE_DIR, "admin/tha_admbnda_adm2_rtsd_20220121.shp")
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


# ---------------- Auth Endpoints ----------------
@app.post("/auth/register", response_model=UserOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already registered")
    user = User(username=data.username, full_name=data.full_name, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid Username or password")
    token = create_access_token(sub=user.username, extra={"uid": user.user_id})
    set_auth_cookie(response, token)
    return user

@app.post("/auth/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}

@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

# ---------------- Init Data Province District ----------------
@app.get("/init_data_province_district")
def init_data_province_district(db: Session = Depends(get_db)):
    if not os.path.exists(PROV_BOUNDARY):
        raise HTTPException(400, f"Province boundary file not found: {PROV_BOUNDARY}")
    try:
        init_data(
            shp_path=PROV_BOUNDARY,
            engine=db
        )
    except Exception as e:
        logger.exception("Init Data Province District failed: %s", e)
        raise HTTPException(400, f"Init Data Province District failed: {e}")
    
    return 'ok'

# ---------------- Upload NetCDF ----------------
@app.post("/upload")
async def upload_netcdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (file.filename.endswith(".nc") or file.content_type in {"application/x-netcdf","application/netcdf"}):
        raise HTTPException(400, "Please upload a .nc file")
    if not os.path.exists(PROV_BOUNDARY):
        raise HTTPException(400, f"Province boundary file not found: {PROV_BOUNDARY}")

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

    row = UploadRainPoint(
        filename=file.filename,
        storage_path=raw_path,
        size_bytes=written,
        content_type=file.content_type or "application/x-netcdf",
        owner_id=user.user_id,
    )
    db.add(row); db.commit(); db.refresh(row)
    try:
        total = ingest_nc_north_adm2_to_db(
            engine=db,
            upload_id=row.upload_id,
            nc_path=raw_path,
            adm2_shp_path=PROV_BOUNDARY,
        )
    except Exception as e:
        logger.exception("ingest failed: %s", e)
        raise HTTPException(400, f"Ingest failed: {e}")

    os.remove(raw_path)
    return {"rows_inserted": total}

# @app.get("/test_upload")
# async def test_upload(
#     db: Session = Depends(get_db),
# ):
#     raw_path = "/data/storage/fe65db3af26643faa135eece3db87758_RAW_chirps-v2.0.2023.days_p05.nc"
#     try:
#         total = ingest_nc_north_adm2_to_db(
#             engine=db,
#             upload_id=1,
#             nc_path=raw_path,
#             adm2_shp_path=PROV_BOUNDARY,
#         )
#     except Exception as e:
#         logger.exception("ingest failed: %s", e)
#         raise HTTPException(400, f"Ingest failed: {e}")


@app.get("/list_province", response_model=ProvinceListOut)
async def list_province(db: Session = Depends(get_db)):
    stmt = (
        select(
            Province.province_id,
            Province.province_name,
            Province.province_name_en,
        )
        .order_by(Province.province_id.asc())
    )

    rows = db.execute(stmt).all()
    items = [
        ProvinceOut(
            province_id=r.province_id,
            province_name=r.province_name,
            province_name_en=r.province_name_en,
        )
        for r in rows
    ]

    return ProvinceListOut(
        total=len(items),
        items=items
    ) 

@app.get("/list_district", response_model=DistrictListOut)
async def list_district(
    province_id: Optional[str] = Query('all', description='เช่น "all" หรือ "50" หรือ "50,51"'),
    db: Session = Depends(get_db)
):
    conds = []
    if province_id != 'all' :
        conds.append(District.province_id == int(province_id))

    stmt = (
        select(
            District.district_id,
            District.district_name,
            District.district_name_en,
        )
        .order_by(District.province_id.asc())
        .order_by(District.district_id.asc())
    )
    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt).all()

    items = [
        DistrictOut(
            district_id=r.district_id,
            district_name=r.district_name,
            district_name_en=r.district_name_en,
        )
        for r in rows
    ]

    return DistrictListOut(
        total=len(items),
        items=items
    ) 


@app.get("/list_rain", response_model=ListPaginationOut)
async def list_rain(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    order_by: str = Query("date", description="field ที่จะใช้ sort"),
    order_type: str = Query("asc", regex="^(asc|desc)$", description="ทิศทาง asc/desc"),
    province_id: Optional[str] = Query('all', description='เช่น "all" หรือ "50" หรือ "50,51"'),
    district_id: Optional[str] = Query('all', description='เช่น "all" หรือ "12"'),
    date_start: Optional[date] = Query(None, description='เช่น "all" หรือ "2024-05-03"'),
    date_end: Optional[date] = Query(None, description='เช่น "all" หรือ "2024-05-03"'),
    db: Session = Depends(get_db),
):
    
    conds = []
    if province_id != 'all' :
        conds.append(RainPoint.province_id == int(province_id))

    if district_id != 'all' :
        conds.append(RainPoint.district_id == int(district_id))

    if date_start is not None and date_start != 'null':
        conds.append(RainPoint.date >= date_start)
    
    if date_end is not None and date_end != 'null':
        conds.append(RainPoint.date <= date_end)


    count_stmt = select(func.count(RainPoint.pk_id)).select_from(RainPoint)
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = db.execute(count_stmt).scalar_one()
    all_page = max((total + page_size - 1) // page_size, 1)
    page = min(page, all_page)

    P = aliased(Province)
    D = aliased(District)

    sortable_fields = {
        "date": RainPoint.date,
        "rain_mm_wmean": RainPoint.rain_mm_wmean,
        "province_name": P.province_name,
        "district_name": D.district_name,
    }

    column = sortable_fields.get(order_by, RainPoint.date)  # fallback = date
    direction = asc if order_type.lower() == "asc" else desc
    stmt = (
        select(
            RainPoint.pk_id,
            RainPoint.date,
            RainPoint.rain_mm_wmean,
            RainPoint.province_id,
            RainPoint.district_id,
            P.province_name.label("province_name"),
            P.province_name_en.label("province_name_en"),
            D.district_name.label("district_name"),
            D.district_name_en.label("district_name_en"),
        )
        .join(P, P.province_id == RainPoint.province_id, isouter=True)
        .join(D, D.district_id == RainPoint.district_id, isouter=True)
        .order_by(direction(column))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt).all()

    items = [
        RainPointOut(
            id=r.pk_id,
            date=r.date,
            rain_mm_wmean=r.rain_mm_wmean,
            province_id=r.province_id,
            district_id=r.district_id,
            province_name=r.province_name,
            province_name_en=r.province_name_en,
            district_name=r.district_name,
            district_name_en=r.district_name_en,
        )
        for r in rows
    ]

    return ListPaginationOut(
        page=page,
        page_size=page_size,
        total=total,
        all_page=all_page,
        items=items,
    )


@app.get("/list_province_district", response_model=ListProvinceDistrictPaginationOut)
async def list_province_district(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    order_by: str = Query("date", description="field ที่จะใช้ sort"),
    order_type: str = Query("asc", regex="^(asc|desc)$", description="ทิศทาง asc/desc"),
    province_id: Optional[str] = Query('all', description='เช่น "all" หรือ "50" หรือ "50,51"'),
    district_id: Optional[str] = Query('all', description='เช่น "all" หรือ "12"'),
    db: Session = Depends(get_db),
):
    
    P = aliased(Province)
    D = aliased(District)
    conds = []
    if province_id != 'all' :
        conds.append(D.province_id == int(province_id))

    if district_id != 'all' :
        conds.append(D.district_id == int(district_id))

   

    count_stmt = select(func.count(D.district_id)).select_from(D)
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = db.execute(count_stmt).scalar_one()
    all_page = max((total + page_size - 1) // page_size, 1)
    page = min(page, all_page)


    sortable_fields = {
        "province_id": D.province_id,
        "province_name": P.province_name,
        "district_name": D.district_name,
    }

    column = sortable_fields.get(order_by, D.province_id)
    direction = asc if order_type.lower() == "asc" else desc
    stmt = (
        select(
            D.province_id,
            D.district_id,
            P.province_name.label("province_name"),
            P.province_name_en.label("province_name_en"),
            D.district_name.label("district_name"),
            D.district_name_en.label("district_name_en"),
        )
        .join(P, P.province_id == D.province_id, isouter=True)
        .order_by(direction(column))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt).all()

    items = [
        ProvinceDistrictPointOut(
            province_id=r.province_id,
            district_id=r.district_id,
            province_name=r.province_name,
            province_name_en=r.province_name_en,
            district_name=r.district_name,
            district_name_en=r.district_name_en,
        )
        for r in rows
    ]

    return ListProvinceDistrictPaginationOut(
        page=page,
        page_size=page_size,
        total=total,
        all_page=all_page,
        items=items,
    )


@app.post("/upload_dbf")
async def upload_dbf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    
    if not (file.filename.endswith(".dbf")):
        raise HTTPException(400, "Please upload a .dbf file")

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

    row = UploadRisk(
        filename=file.filename,
        storage_path=raw_path,
        size_bytes=written,
        content_type=file.content_type,
        owner_id=user.user_id,
    )
    db.add(row); db.commit(); db.refresh(row)

    special_fix = False
    if(file.filename == 'landslide_utt.dbf'):
        special_fix = True
    try:
        total = ingest_dbf_to_db(
            engine=db,
            upload_risk_id=row.upload_risk_id,
            raw_path=raw_path,
            special_fix=special_fix
        )
    except Exception as e:
        logger.exception("ingest failed: %s", e)
        raise HTTPException(400, f"Ingest failed: {e}")

    os.remove(raw_path)
    return {"rows_inserted": total}

@app.get("/list_risk", response_model=ListRiskPaginationOut)
async def list_risk(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    order_by: str = Query("date", description="field ที่จะใช้ sort"),
    order_type: str = Query("asc", regex="^(asc|desc)$", description="ทิศทาง asc/desc"),
    province_id: Optional[str] = Query('all', description='เช่น "all" หรือ "50" หรือ "50,51"'),
    district_id: Optional[str] = Query('all', description='เช่น "all" หรือ "12"'),
    risk_level: Optional[str] = Query('all', description='เช่น "all" หรือ "12"'),
    db: Session = Depends(get_db),
):
    
    conds = []
    if province_id != 'all' :
        conds.append(RiskPoint.province_id == int(province_id))

    if district_id != 'all' :
        conds.append(RiskPoint.district_id == int(district_id))

    if risk_level != 'all' :
        conds.append(RiskPoint.risk_level == int(risk_level))


    count_stmt = select(func.count(RiskPoint.risk_id)).select_from(RiskPoint)
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = db.execute(count_stmt).scalar_one()
    all_page = max((total + page_size - 1) // page_size, 1)
    page = min(page, all_page)

    P = aliased(Province)
    D = aliased(District)

    sortable_fields = {
        "risk_level": RiskPoint.risk_level,
        "province_name": P.province_name,
        "district_name": D.district_name,
    }

    column = sortable_fields.get(order_by, D.province_id)
    direction = asc if order_type.lower() == "asc" else desc
    stmt = (
        select(
            RiskPoint.risk_id,
            RiskPoint.risk_level,
            RiskPoint.province_id,
            RiskPoint.district_id,
            P.province_name.label("province_name"),
            P.province_name_en.label("province_name_en"),
            D.district_name.label("district_name"),
            D.district_name_en.label("district_name_en"),
        )
        .join(P, P.province_id == RiskPoint.province_id, isouter=True)
        .join(D, D.district_id == RiskPoint.district_id, isouter=True)
        .order_by(direction(column))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt).all()

    items = [
        RiskPointOut(
            id=r.risk_id,
            risk_level=r.risk_level,
            province_id=r.province_id,
            district_id=r.district_id,
            province_name=r.province_name,
            province_name_en=r.province_name_en,
            district_name=r.district_name,
            district_name_en=r.district_name_en,
        )
        for r in rows
    ]

    return ListRiskPaginationOut(
        page=page,
        page_size=page_size,
        total=total,
        all_page=all_page,
        items=items,
    )


@app.post("/upload_excel")
async def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ .xlsx หรือ .xls")
    try:
        result = await ingest_excel_to_db(
            engine=db,
            file=file,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"อ่านไฟล์ไม่สำเร็จ: {e}")

@app.get("/list_incident_statistics", response_model=ListIncidentStatisticsPaginationOut)
async def list_incident_statistics(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    order_by: str = Query("date", description="field ที่จะใช้ sort"),
    order_type: str = Query("asc", regex="^(asc|desc)$", description="ทิศทาง asc/desc"),
    province_id: Optional[str] = Query('all', description='เช่น "all" หรือ "50" หรือ "50,51"'),
    district_id: Optional[str] = Query('all', description='เช่น "all" หรือ "12"'),
    date_start: Optional[date] = Query(None, description='เช่น "all" หรือ "2024-05-03"'),
    date_end: Optional[date] = Query(None, description='เช่น "all" หรือ "2024-05-03"'),
    db: Session = Depends(get_db),
):
    
        
    
    conds = []
    if province_id != 'all' :
        conds.append(IncidentStatisticsPoint.province_id == int(province_id))

    if district_id != 'all' :
        conds.append(IncidentStatisticsPoint.district_id == int(district_id))

    if date_start is not None and date_start != 'null':
        conds.append(IncidentStatisticsPoint.disaster_date >= date_start)
    
    if date_end is not None and date_end != 'null':
        conds.append(IncidentStatisticsPoint.disaster_date <= date_end)


    count_stmt = select(func.count(IncidentStatisticsPoint.incident_id)).select_from(IncidentStatisticsPoint)
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = db.execute(count_stmt).scalar_one()
    all_page = max((total + page_size - 1) // page_size, 1)
    page = min(page, all_page)

    P = aliased(Province)
    D = aliased(District)

    sortable_fields = {
        "disaster_date": IncidentStatisticsPoint.disaster_date,
        "count_of_disasters": IncidentStatisticsPoint.count_of_disasters,
        "province_name": P.province_name,
        "district_name": D.district_name,
    }

    column = sortable_fields.get(order_by, D.province_id)
    direction = asc if order_type.lower() == "asc" else desc
    stmt = (
        select(
            IncidentStatisticsPoint.incident_id,
            IncidentStatisticsPoint.disaster_date,
            IncidentStatisticsPoint.province_id,
            IncidentStatisticsPoint.district_id,
            IncidentStatisticsPoint.count_of_disasters,
            P.province_name.label("province_name"),
            P.province_name_en.label("province_name_en"),
            D.district_name.label("district_name"),
            D.district_name_en.label("district_name_en"),
        )
        .join(P, P.province_id == IncidentStatisticsPoint.province_id, isouter=True)
        .join(D, D.district_id == IncidentStatisticsPoint.district_id, isouter=True)
        .order_by(direction(column))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt).all()

    items = [
        IncidentStatisticsPointOut(
            id=r.incident_id,
            disaster_date=r.disaster_date,
            count_of_disasters=r.count_of_disasters,
            province_id=r.province_id,
            district_id=r.district_id,
            province_name=r.province_name,
            province_name_en=r.province_name_en,
            district_name=r.district_name,
            district_name_en=r.district_name_en,
        )
        for r in rows
    ]
    	

    return ListIncidentStatisticsPaginationOut(
        page=page,
        page_size=page_size,
        total=total,
        all_page=all_page,
        items=items,
    )