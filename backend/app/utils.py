from __future__ import annotations
import os, io, csv, logging
from typing import List, Tuple, Optional
import numpy as np
import xarray as xr
import shapefile  # pyshp
import pandas as pd
from shapely.geometry import shape as shp_shape, Point, Polygon, MultiPolygon, box as shp_box
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree
from shapely import points as shp_points  # shapely>=2.0

logger = logging.getLogger("utils")

# ------------------------- Helper: Table summary -------------------------
def summarize_table(path: str) -> dict:
    """
    อ่านไฟล์ .csv / .xlsx แบบง่าย ๆ เพื่อสรุปจำนวนแถว/คอลัมน์ และ preview 5 แถว
    """
    try:
        if path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path)
        else:
            try:
                df = pd.read_csv(path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="cp874")
    except Exception as e:
        raise RuntimeError(f"Failed to read table: {e}")

    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "preview": df.head(5).to_dict(orient="records"),
    }

# ---------------------- Normalization & ENV helpers ----------------------
DEFAULT_NORTH_EN = [
    "Chiang Mai","Chiang Rai","Lamphun","Lampang","Mae Hong Son",
    "Phayao","Phrae","Nan","Uttaradit","Phitsanulok",
    "Sukhothai","Tak","Kamphaeng Phet","Nakhon Sawan",
    "Phichit","Phetchabun","Uthai Thani",
]

def _norm_name(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    for pref in ("จังหวัด", "Changwat"):
        if s.startswith(pref):
            s = s[len(pref):].strip()
    # normalize whitespace
    s = " ".join(s.split())
    # try title-case english (ไทยคงเดิม)
    try:
        s.encode("ascii")
        s = s.title()
    except Exception:
        pass
    return s

def _north_set_from_env() -> set[str]:
    env = os.getenv("NORTH_PROVS_EN", "").strip()
    if env:
        return {_norm_name(x) for x in env.split(",") if x.strip()}
    return {_norm_name(x) for x in DEFAULT_NORTH_EN}

# --------------------- Shapefile (ADM2) loading for North ----------------
def _load_adm2_north(adm2_shp_path: str):
    """
    อ่าน shapefile ระดับอำเภอ (adm2) แล้วคัดเฉพาะจังหวัด 'ภาคเหนือ'
    คืน:
      polys:   list[Polygon|MultiPolygon]
      attrs:   list[(province, district)]
      tree:    STRtree ของ polys
      union:   union polygon ของทั้งหมด (ใช้ตัด bbox)
    รองรับฟิลด์ชื่อที่พบบ่อย: NAME_1 / NL_NAME_1 / PROV_NAM_T / PROV_NAM_E
                            และ NAME_2 / NL_NAME_2 / ADM2_EN / ADM2_TH
    """
    r = shapefile.Reader(adm2_shp_path)
    fields = [f[0] for f in r.fields if f[0] != "DeletionFlag"]

    prov_candidates = ["NAME_1", "NL_NAME_1", "PROV_NAM_T", "PROV_NAM_E"]
    dist_candidates = ["NAME_2", "NL_NAME_2", "ADM2_EN", "ADM2_TH"]

    prov_field = next((c for c in prov_candidates if c in fields), None)
    dist_field = next((c for c in dist_candidates if c in fields), None)
    if not prov_field or not dist_field:
        raise RuntimeError(f"Require province/district fields. Found fields={fields}")

    north = _north_set_from_env()

    polys: List[Polygon | MultiPolygon] = []
    attrs: List[Tuple[str, str]] = []

    for sr in r.shapeRecords():
        rec = {fields[i]: sr.record[i] for i in range(len(fields))}
        prov = _norm_name(rec.get(prov_field, ""))
        if prov not in north:
            continue
        dist = _norm_name(rec.get(dist_field, ""))
        geom = shp_shape(sr.shape.__geo_interface__)
        if isinstance(geom, (Polygon, MultiPolygon)):
            polys.append(geom)
            attrs.append((prov, dist))

    if not polys:
        # debug: โชว์จังหวัดที่อ่านได้จริง ๆ เพื่อช่วยตั้ง NORTH_PROVS_TH
        found_provs = set()
        for sr in r.shapeRecords()[:50]:
            rec = {fields[i]: sr.record[i] for i in range(len(fields))}
            found_provs.add(_norm_name(rec.get(prov_field, "")))
        raise RuntimeError(
            f"No northern districts found. "
            f"Check province names or NORTH_PROVS_TH. Sample provs={sorted(found_provs)[:15]}"
        )

    tree = STRtree(polys)
    union_poly = unary_union(polys)
    return polys, attrs, tree, union_poly

# --------------------------- Grid slicing helper -------------------------
def _slice_to_bbox(lat: np.ndarray, lon: np.ndarray, poly_union: Polygon | MultiPolygon):
    minx, miny, maxx, maxy = poly_union.bounds  # lon_min, lat_min, lon_max, lat_max
    if lat[0] <= lat[-1]:
        ilat = np.where((lat >= miny) & (lat <= maxy))[0]
    else:
        ilat = np.where((lat <= maxy) & (lat >= miny))[0]
    if lon[0] <= lon[-1]:
        ilon = np.where((lon >= minx) & (lon <= maxx))[0]
    else:
        ilon = np.where((lon <= maxx) & (lon >= minx))[0]
    if ilat.size == 0 or ilon.size == 0:
        return None, None
    return (ilat.min(), ilat.max() + 1), (ilon.min(), ilon.max() + 1)

# --------------------- COPY helper (psycopg2 / psycopg3) -----------------
def _copy_rows(cur, sql_copy: str, rows: List[Tuple]):
    """
    รองรับทั้ง psycopg2 (cursor.copy_expert) และ psycopg3 (cursor.copy)
    """
    if not rows:
        return
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    data = buf.getvalue()

    if hasattr(cur, "copy_expert"):  # psycopg2
        cur.copy_expert(sql_copy, io.StringIO(data))
    elif hasattr(cur, "copy"):       # psycopg3
        with cur.copy(sql_copy) as cp:
            cp.write(data.encode("utf-8"))
    else:
        # fallback (ช้ากว่า): executemany insert
        cur.executemany(
            "INSERT INTO rain_points (dataset_id, date, year, province, district, lat, lon, rainfall_mm) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )

# ---------------------- Ingest NetCDF -> Postgres rows -------------------
def ingest_nc_north_adm2_to_db(
    engine,
    dataset_id: int,
    nc_path: str,
    var_name: str,                 # ชื่อตัวแปรฝนในไฟล์ .nc (เช่น "precip")
    adm2_shp_path: str,            # path ไปยัง GADM level 2 (.shp)
    table_name: str = "rain_points",
) -> int:
    """
    เปิด .nc → ตัดเฉพาะ bbox ภาคเหนือ → ไล่ไทล์ → map พิกัดไปยัง (จังหวัด, อำเภอ)
    แล้ว COPY ลง Postgres แบบ batch
    Columns: dataset_id, date(YYYY-MM-DD), year, province, district, lat, lon, rainfall_mm
    """
    polys, attrs, tree, union_poly = _load_adm2_north(adm2_shp_path)
    prepared_polys = [prep(g) for g in polys]
    prepared_union = prep(union_poly)

    ds = xr.open_dataset(nc_path, engine="netcdf4")
    try:
        lat_name = "lat" if "lat" in ds.coords else "latitude"
        lon_name = "lon" if "lon" in ds.coords else "longitude"
        time_name = "time" if "time" in ds.coords else None

        if var_name not in ds.data_vars:
            raise RuntimeError(f"Variable '{var_name}' not found. Found: {list(ds.data_vars)}")

        lat = ds[lat_name].values
        lon = ds[lon_name].values

        # ตัดกรอบ bbox
        rr, cc = _slice_to_bbox(lat, lon, union_poly)
        if rr is None:
            logger.info("No overlap with northern union polygon; nothing to ingest.")
            return 0

        (i0, i1), (j0, j1) = rr, cc
        lat_sub = lat[i0:i1]
        lon_sub = lon[j0:j1]
        da = ds[var_name].isel({lat_name: slice(i0, i1), lon_name: slice(j0, j1)})

        # thinning (ลดจำนวนจุด/แถว)
        s_lat = max(1, int(os.getenv("INGEST_LAT_STRIDE", "1")))
        s_lon = max(1, int(os.getenv("INGEST_LON_STRIDE", "1")))
        lat_idx = np.arange(0, lat_sub.size, s_lat)
        lon_idx = np.arange(0, lon_sub.size, s_lon)
        lat_sub = lat_sub[lat_idx]
        lon_sub = lon_sub[lon_idx]
        da = da.isel({lat_name: lat_idx, lon_name: lon_idx})

        # เตรียมเวลา
        if time_name and time_name in da.dims:
            times = ds[time_name].values
            T = da.sizes[time_name]
        else:
            times = [None]
            T = 1

        # เตรียม DB
        conn = engine.raw_connection()
        cur = conn.cursor()
        inserted = 0

        sql_copy = (
            f"COPY {table_name} "
            "(dataset_id, date, year, province, district, lat, lon, rainfall_mm) "
            "FROM STDIN WITH (FORMAT csv)"
        )

        def _flush(rows: List[Tuple]):
            nonlocal inserted
            if not rows:
                return
            _copy_rows(cur, sql_copy, rows)
            inserted += len(rows)

        tile_h = int(os.getenv("CLIP_TILE_H", "256"))
        tile_w = int(os.getenv("CLIP_TILE_W", "256"))

        for t_idx in range(T):
            if times[t_idx] is not None:
                # แปลงเป็น YYYY-MM-DD และ year
                ts = np.datetime64(times[t_idx], "us").astype("datetime64[ms]")
                ts_iso = str(ts)[:10]
                year = int(str(ts)[:4])
                slab = da.isel({time_name: t_idx})
            else:
                ts_iso = None
                year = None
                slab = da

            vals = slab.values  # 2D array

            rows: List[Tuple] = []
            H, W = lat_sub.size, lon_sub.size

            for r0 in range(0, H, tile_h):
                r1 = min(r0 + tile_h, H)
                lats = lat_sub[r0:r1]
                lat_min, lat_max = lats.min(), lats.max()

                for c0 in range(0, W, tile_w):
                    c1 = min(c0 + tile_w, W)
                    lons = lon_sub[c0:c1]
                    lon_min, lon_max = lons.min(), lons.max()

                    tile_box = shp_box(lon_min, lat_min, lon_max, lat_max)

                    # ข้ามไทล์ที่อยู่นอก union ทั้งหมด
                    if prepared_union.disjoint(tile_box):
                        continue

                    # ผู้สมัคร polygon ในไทล์นี้
                    cand_idx = tree.query(tile_box)
                    cand_idx = cand_idx.tolist() if hasattr(cand_idx, "tolist") else list(cand_idx)

                    cand_prepared = [prepared_polys[int(i)] for i in cand_idx]
                    cand_attrs    = [attrs[int(i)]          for i in cand_idx]

                    LON, LAT = np.meshgrid(lons, lats)
                    pts = shp_points(LON.ravel(), LAT.ravel())

                    tile_h_ = (r1 - r0)
                    tile_w_ = (c1 - c0)
                    unmatched = 0

                    for k, pt in enumerate(pts):
                        ii = r0 + (k // tile_w_)
                        jj = c0 + (k %  tile_w_)

                        v = vals[ii, jj]
                        if np.isnan(v):
                            continue

                        found = False
                        for pprep, (prov, dist) in zip(cand_prepared, cand_attrs):
                            if pprep.covers(pt):  # covers รวมกรณีบนขอบ
                                rows.append((
                                    dataset_id,
                                    ts_iso,
                                    year,
                                    prov,
                                    dist,
                                    float(lat_sub[ii]),
                                    float(lon_sub[jj]),
                                    float(v),
                                ))
                                found = True
                                break
                        if not found:
                            unmatched += 1

                        if len(rows) >= 200_000:
                            _flush(rows); rows = []

                    if unmatched:
                        logger.info(f"tile r{r0}:{r1} c{c0}:{c1} unmatched={unmatched}")

            _flush(rows)
            logger.info(f"ingested time={ts_iso} total_rows={inserted}")

        conn.commit()
        cur.close(); conn.close()
        return inserted

    finally:
        ds.close()
