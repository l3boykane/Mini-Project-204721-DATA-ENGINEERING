from __future__ import annotations
import os, logging, re
import numpy as np
import xarray as xr
import pandas as pd
import unicodedata
import geopandas as gpd
from dbfread import DBF

from .models import Province, District, UploadRisk

logger = logging.getLogger("utils")
# ---------------------- Ingest NetCDF -> Postgres rows -------------------

def clean_text(x):
    if pd.isna(x):
        return x
    s = str(x)
    # แทนตัวขึ้นบรรทัดด้วยช่องว่าง ป้องกัน CSV ตกบรรทัด
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    s = s.replace("จังหวัด", "").replace("กิ่งอำเภอ", "").replace("อำเภอ", "").replace("K. ", "")
    s = s.replace("Muang", "Mueang").replace("Wieng", "Wiang")
    # normalize รูปแบบตัวอักษร (กันสระลอย/ผสมเพี้ยนบางกรณี)
    s = unicodedata.normalize("NFC", s)
    return s


def ingest_nc_north_adm2_to_db(
    engine,
    upload_id: int,
    nc_path: str,
    adm2_shp_path: str,
) -> int:
    """
    เขียนลงตารางเดิม 'rain_points' แบบ 'หนึ่งแถวต่ออำเภอต่อวัน'
    - เร็วเท่ากับตอนก่อนแก้ (ไม่เขียนทุก grid)
    - เติม lat/lon จาก centroid ของ polygon อำเภอ เพื่อผ่าน NOT NULL
    """

    # ---------- 1) โหลด province/district mapping จาก DB เป็น DataFrame ----------
    rows = engine.query(
        Province.province_id, Province.province_name, Province.province_name_en
    ).all()
    provinces_df = pd.DataFrame(rows, columns=["province_id","province_name","province_name_en"])

    rows = engine.query(
        District.district_id, District.province_id, District.district_name, District.district_name_en
    ).all()
    districts_df = pd.DataFrame(rows, columns=["district_id","province_id","district_name","district_name_en"])

    provinces_df["key_en"] = provinces_df["province_name_en"].map(clean_text)
    districts_df["key_en"] = districts_df["district_name_en"].map(clean_text)

    # ---------- 2) เปิด NetCDF + ตัด bbox ไทย ----------
    ds = xr.open_dataset(nc_path)
    lon = ds["longitude"]
    if float(lon.max()) > 180:
        lon2 = ((lon + 180) % 360) - 180
        ds = ds.assign_coords(longitude=lon2).sortby("longitude")

    lat_min, lat_max = 5.6, 20.5
    lon_min, lon_max = 97.3, 105.7
    ds_th = ds.sel(latitude=slice(lat_min, lat_max), longitude=slice(lon_min, lon_max))
    da = ds_th["precip"]

    # DataFrame point-level (แค่ใช้คำนวณ aggregate)
    df_values = da.to_dataframe(name="precip").reset_index()

    # ---------- 3) โหลด shapefile ADM2 และกรองเฉพาะภาคเหนือ ----------
    adm2 = gpd.read_file(adm2_shp_path).to_crs("EPSG:4326")

    north_env = os.getenv(
        "NORTH_PROVS_EN",
        "Chiang Mai,Chiang Rai,Lamphun,Lampang,Phayao,Phrae,Nan,Mae Hong Son,Uttaradit"
    )
    north_list = [x.strip() for x in north_env.split(",")]

    adm2_north = adm2[adm2["ADM1_EN"].isin(north_list)][["ADM1_EN","ADM2_EN","geometry"]].copy()
    adm2_north = adm2_north.rename(columns={"ADM1_EN":"province","ADM2_EN":"district"})

    # ---------- 4) sjoin จุดกริดกับขอบเขตอำเภอ → เพื่อคำนวณสรุประดับอำเภอ ----------
    gdf_points = gpd.GeoDataFrame(
        df_values,
        geometry=gpd.points_from_xy(df_values["longitude"], df_values["latitude"]),
        crs="EPSG:4326"
    )
    gdf_joined = gpd.sjoin(gdf_points, adm2_north, how="inner", predicate="within")
    # ตอนนี้มีคอลัมน์: time, latitude, longitude, precip, province, district

    # ---------- 5) คำนวณค่าเฉลี่ยถ่วงน้ำหนัก + ปริมาณรวม (ต่ออำเภอ/วัน) ----------
    gdf_joined["weight"] = np.cos(np.deg2rad(gdf_joined["latitude"]))

    # weighted mean (หลีกเลี่ยง FutureWarning)
    daily_wmean = (
        gdf_joined.groupby(["time","province","district"], observed=True)
        .apply(lambda df: np.average(df["precip"].to_numpy(),
                                     weights=df["weight"].to_numpy()))
        .rename("rain_mm_wmean").reset_index()
    )

    # area + volume รวม (ล้าน m³)
    dlat = float(np.abs(np.diff(sorted(gdf_joined["latitude"].unique()))).min())
    dlon = float(np.abs(np.diff(sorted(gdf_joined["longitude"].unique()))).min())
    km_per_deg = 111.32
    gdf_joined["cell_area_km2"] = (
        km_per_deg * dlat * km_per_deg * dlon * np.cos(np.deg2rad(gdf_joined["latitude"]))
    )
    gdf_joined["rainfall_mm"] = (
        gdf_joined["precip"] * gdf_joined["cell_area_km2"] * 1000 / 1e6
    )
    daily_sum = (
        gdf_joined.groupby(["time","province","district"], observed=True)["rainfall_mm"]
        .sum().reset_index()
    )

    daily_result = daily_wmean.merge(daily_sum, on=["time","province","district"], how="left")

    # ---------- 6) map province/district → id (ใช้ key อังกฤษ) ----------
    daily_result["prov_key"] = daily_result["province"].map(clean_text)
    daily_result["dist_key"] = daily_result["district"].map(clean_text)

    daily_result = daily_result.merge(
        provinces_df[["province_id","key_en"]].rename(columns={"key_en":"prov_key"}),
        on="prov_key", how="left"
    )
    daily_result = daily_result.merge(
        districts_df[["district_id","province_id","key_en"]].rename(columns={"key_en":"dist_key"}),
        on=["province_id","dist_key"], how="left"
    )


    # ตัดแถวที่ยังไม่มี id/centroid (กัน NOT NULL)
    before = len(daily_result)
    daily_result = daily_result.dropna(subset=["province_id","district_id"]).copy()
    after = len(daily_result)


    # ---------- 8) จัดรูปคอลัมน์ตรง schema 'rain_points' ----------
    daily_result["date"] = pd.to_datetime(daily_result["time"]).dt.date
    daily_result["year"] = pd.to_datetime(daily_result["time"]).dt.year
    daily_result["upload_id"] = upload_id

    df_points = daily_result[[
        "upload_id", "date", "year",
        "province_id", "district_id",
        "rain_mm_wmean",
        "rainfall_mm" 
    ]].copy()

    df_points["district_id"] = df_points["district_id"].astype(int)
    df_points["province_id"] = df_points["province_id"].astype(int)
    df_points["year"]        = df_points["year"].astype(int)
    df_points["rainfall_mm"] = df_points["rainfall_mm"].fillna(0.0).astype(float)


    # ---------- 9) insert ด้วย Engine/Connection จาก Session (ก้อนเดียว) ----------
    # print(f"➡️  will insert rows: {len(df_points):,} (dropped {before-after:,} rows with missing id/centroid)")
    bind = engine.get_bind()  # ได้ Engine/Connection จริง
    with bind.begin() as conn:
        df_points.to_sql(
            "rain_points",
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=2000
        )


    return len(df_points)


def init_data (engine, shp_path: str):
    gdf = gpd.read_file(shp_path, encoding="utf-8")
    if gdf.geometry.name not in gdf.columns or gdf.geometry.dtype.name != "geometry":
        if "geometry" in gdf.columns:
            from shapely import wkt
            gdf = gpd.GeoDataFrame(
                gdf.drop(columns=["geometry"]),
                geometry=gdf["geometry"].apply(lambda s: wkt.loads(s) if pd.notna(s) else None),
                crs="EPSG:4326"
            )

    df = gdf.copy()
    df["geometry"] = df.geometry.apply(lambda g: g.wkt if g is not None else None)
    NORTH_PROVS_EN = os.getenv("NORTH_PROVS_EN")
    NORTH_PROVS_EN_LIST = NORTH_PROVS_EN.split(',')
    finalDF = {}

    filtered_df = df[df['ADM1_EN'].isin(NORTH_PROVS_EN_LIST)]

    for _, row in filtered_df.iterrows():
        prov_en = clean_text(row['ADM1_EN'])
        prov_th = clean_text(row['ADM1_TH'])
        dist_en = clean_text(row['ADM2_EN'])
        dist_th = clean_text(row['ADM2_TH'])

        if prov_en not in finalDF:
            finalDF[prov_en] = {
                "th": prov_th,
                "districts": []
            }

        finalDF[prov_en]["districts"].append({
            "en": dist_en,
            "th": dist_th
        })

    for row in finalDF:
        is_engine = False
        pid = 0
        dataP = engine.query(Province).filter(Province.province_name_en == row.strip()).first()
        if dataP is None:
            p = Province(province_name=finalDF[row]['th'].strip(), province_name_en=row.strip())
            engine.add(p)
            engine.flush() 
            pid = p.province_id
            is_engine = True
        else: 
            pid = dataP.province_id
            
        for rowD in finalDF[row]['districts']:
            if engine.query(District).filter(District.district_name_en == rowD['en'].strip(), District.province_id == pid).first() is None:
                engine.add(District(
                    district_name=rowD['th'].strip(),
                    district_name_en=rowD['en'].strip(),
                    province_id=pid
                ))
                is_engine = True

        if is_engine:
            engine.commit()

def class_to_num(x):
    text_to_num = {
        "ต่ำ": 1, "ต่ำมาก": 1, "low": 1, "very low": 1,
        "ปานกลาง": 2, "กลาง": 2, "medium": 2,
        "สูง": 3, "สูงมาก": 3, "high": 3, "very high": 3
    }
    # ถ้าเป็นเลขอยู่แล้ว
    try:
        val = float(x)
        if 0 <= val <= 1:
            if val < 1/3: return 1
            elif val < 2/3: return 2
            else: return 3
        val = int(round(val))
        return max(1, min(3, val))
    except Exception:
        pass
    # ถ้าเป็นข้อความ
    s = str(x).strip().lower()
    return text_to_num.get(s, None)

def normalize_th(s: str) -> str:
    """ตัดช่องว่างหัว-ท้าย ยุบช่องว่างซ้ำ เป็นคีย์จับคู่แบบเรียบง่าย"""
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("จ.", "").replace("อ.", "")

    return s

def ingest_dbf_to_db(
    engine,
    upload_risk_id: int,
    raw_path: str,
    special_fix: bool=False
) -> int:
    # ---------- 0) โหลด DBF ----------
    table = DBF(raw_path, load=True, encoding="tis-620")
    df_dbf = pd.DataFrame(iter(table))

    # ตรวจคอลัมน์ (รองรับ case-insensitive)
    df_dbf = df_dbf.rename(columns={col: col.lower() for col in df_dbf.columns})
    required_cols = {"amphoe_t", "prov_nam_t", "class"}
    missing = required_cols - set(df_dbf.columns)
    if missing:
        print("⚠️ columns ใน DBF:", list(df_dbf.columns))
        raise KeyError("ไม่พบคอลัมน์สำคัญใน DBF (คาดว่า amphoe_t, prov_nam_t, class)")

    # ---------- 1) เตรียมข้อมูลจาก DB ----------
    rows = engine.query(
        Province.province_id, Province.province_name, Province.province_name_en
    ).all()
    provinces_df = pd.DataFrame(rows, columns=["province_id","province_name","province_name_en"])

    rows = engine.query(
        District.district_id, District.province_id, District.district_name, District.district_name_en
    ).all()
    districts_df = pd.DataFrame(rows, columns=["district_id","province_id","district_name","district_name_en"])

    # คีย์ normalize
    provinces_df = provinces_df.copy()
    districts_df = districts_df.copy()
    provinces_df["prov_key"] = provinces_df["province_name"].astype(str).map(normalize_th)
    districts_df["dist_key"] = districts_df["district_name"].astype(str).map(normalize_th)

    if special_fix:
        # fix ให้ทุกแถวเป็นจังหวัด "อุตรดิตถ์" ไปเลย
        utt = provinces_df.loc[provinces_df["province_name_en"]=="Uttaradit"].iloc[0]
        target_key = normalize_th(utt.province_name)

        # เลือกเฉพาะแถวที่ prov_nam_t ไม่ตรงกับจังหวัดจริงใน DB
        known_prov_keys = set(provinces_df["prov_key"])
        bad_mask = ~df_dbf["prov_nam_t"].isin(known_prov_keys)

        if bad_mask.any():
            df_dbf.loc[bad_mask, "prov_nam_t"] = target_key
            print(f"⚠️ special_fix: set province → Uttaradit ({utt.province_name})")

    # district + province metadata
    dist_with_prov = districts_df.merge(
        provinces_df[["province_id","prov_key","province_name","province_name_en"]],
        on="province_id",
        how="left",
        validate="many_to_one"
    ).rename(columns={"prov_key":"prov_key_db"})

    # ---------- 2) เตรียมข้อมูลจากไฟล์ ----------
    df_dbf["amphoe_t"]   = df_dbf["amphoe_t"].astype(str).map(normalize_th)
    df_dbf["prov_nam_t"] = df_dbf["prov_nam_t"].astype(str).map(normalize_th)

    # map ระดับชั้นเป็นตัวเลข
    df_dbf["class_num"] = df_dbf["class"].apply(class_to_num)
    unknown = df_dbf[df_dbf["class_num"].isna()]["class"].drop_duplicates()
    if len(unknown) > 0:
        print("⚠️ พบ class ที่ยัง map ไม่ได้:", unknown.to_list())

    # สรุปเฉลี่ยความเสี่ยงต่อ (จังหวัด, อำเภอ)
    risk_by_amp = (
        df_dbf.dropna(subset=["class_num"])
             .groupby(["prov_nam_t","amphoe_t"], as_index=False)["class_num"]
             .mean()
             .rename(columns={"class_num":"risk_avg"})
    )

    def avg_to_level(x: float) -> int:
        if x <= 1.5: return 1
        elif x <= 2.1: return 2
        elif x > 2.1: return 3
        else: return 3

    risk_by_amp["risk_level"] = risk_by_amp["risk_avg"].apply(avg_to_level)
    risk_by_amp["prov_key"] = risk_by_amp["prov_nam_t"]
    risk_by_amp["dist_key"] = risk_by_amp["amphoe_t"]

    # ---------- 3) จับคู่ (จังหวัด, อำเภอ) กับข้อมูลใน DB ----------
    matched = risk_by_amp.merge(
        dist_with_prov,
        left_on=["prov_key","dist_key"],
        right_on=["prov_key_db","dist_key"],
        how="left",
        indicator=True,
        validate="one_to_many"
    )

    # ---------- 4) เติมอำเภอที่ "ขาด" ด้วย risk_level=1 ----------
    # 4.1 หา "ชุดจังหวัด" ที่ปรากฏในไฟล์ (prov_key ที่เจอใน risk_by_amp)
    prov_keys_in_file = set(risk_by_amp["prov_key"].unique())

    # 4.2 map prov_key -> province_id ที่มีอยู่จริง (normalize ด้วย prov_key)
    prov_map = provinces_df[["province_id","prov_key"]].drop_duplicates()
    prov_ids_in_file = prov_map[prov_map["prov_key"].isin(prov_keys_in_file)]["province_id"].unique()

    # 4.3 ดึง "อำเภอทั้งหมด" ของจังหวัดที่อยู่ในไฟล์
    all_districts_in_those_provs = dist_with_prov[dist_with_prov["province_id"].isin(prov_ids_in_file)][
        ["province_id","district_id","dist_key","prov_key_db"]
    ].drop_duplicates()

    # 4.4 หาอำเภอที่ยังไม่ถูกแมตช์ (คือยังไม่มี district_id ใน matched ที่จบแล้ว)
    matched_ok = matched[~matched["district_id"].isna()][["province_id","district_id"]].drop_duplicates()
    missing_districts = all_districts_in_those_provs.merge(
        matched_ok, on=["province_id","district_id"], how="left", indicator=True
    )
    missing_districts = missing_districts[missing_districts["_merge"]=="left_only"].drop(columns=["_merge"])

    # 4.5 สร้างแถวเติม risk_level=1 สำหรับอำเภอที่ขาด
    # เงื่อนไข: ต้องแน่ใจว่า "จังหวัดนั้น" พบในไฟล์จริงๆ (โดยใช้ prov_key_db ที่อยู่ในรายการ prov_keys_in_file)
    missing_districts = missing_districts[missing_districts["prov_key_db"].isin(prov_keys_in_file)].copy()
    fill_df = missing_districts[["province_id","district_id"]].copy()
    fill_df["risk_level"] = 1
    fill_df["upload_risk_id"] = int(upload_risk_id)

    # ---------- 5) เตรียมผลลัพธ์สำหรับเขียนลง DB ----------
    result_matched = (
        matched[["province_id","district_id","risk_level"]]
        .dropna(subset=["province_id","district_id","risk_level"])
        .astype({"province_id":"int64","district_id":"int64","risk_level":"int64"})
        .drop_duplicates(subset=["district_id"])
        .reset_index(drop=True)
    )
    result_matched["upload_risk_id"] = int(upload_risk_id)

    # รวมผลที่แมตช์ได้ + แถวเติม
    result = pd.concat([result_matched, fill_df], ignore_index=True).drop_duplicates(
        subset=["district_id","upload_risk_id"], keep="first"
    )

    # ---------- 6) เขียนลง DB ----------
    bind = engine.get_bind()
    with bind.begin() as conn:
        result.to_sql(
            "risk_points",
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=2000
        )

    return int(len(result))




            