from __future__ import annotations
import os, logging
import numpy as np
import xarray as xr
import pandas as pd
import unicodedata
import geopandas as gpd

from .models import Province, District

logger = logging.getLogger("utils")
# ---------------------- Ingest NetCDF -> Postgres rows -------------------

def clean_text(x):
    if pd.isna(x):
        return x
    s = str(x)
    # แทนตัวขึ้นบรรทัดด้วยช่องว่าง ป้องกัน CSV ตกบรรทัด
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    s = s.replace("จังหวัด", "").replace("กิ่งอำเภอ", "").replace("อำเภอ", "").replace("K. ", "").replace("เมืองเพชรบูรณ์", "เพชรบูรณ์")
    s = s.replace("Muang", "Mueang").replace("Wieng", "Wiang")
    # normalize รูปแบบตัวอักษร (กันสระลอย/ผสมเพี้ยนบางกรณี)
    s = unicodedata.normalize("NFC", s)
    return s


def ingest_nc_north_adm2_to_db(
    engine,                # <-- นี่คือ SQLAlchemy Session ของคุณ (ตามที่ใช้อยู่)
    upload_id: int,
    nc_path: str,
    adm2_shp_path: str,    # path ไปยัง GADM level 2 (.shp)
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

    adm2_north = adm2[adm2["NAME_1"].isin(north_list)][["NAME_1","NAME_2","geometry"]].copy()
    adm2_north = adm2_north.rename(columns={"NAME_1":"province","NAME_2":"district"})

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

    filtered_df = df[df['NAME_1'].isin(NORTH_PROVS_EN_LIST)]

    for _, row in filtered_df.iterrows():
        prov_en = clean_text(row['NAME_1'])
        prov_th = clean_text(row['NL_NAME_1'])
        dist_en = clean_text(row['NAME_2'])
        dist_th = clean_text(row['NL_NAME_2'])

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