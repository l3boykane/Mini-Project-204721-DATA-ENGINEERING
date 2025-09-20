from sqlalchemy import Column, Integer, String, DateTime, Date, Index, JSON, Text, ForeignKey, BigInteger, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
	__tablename__ = "users"
	id = Column(Integer, primary_key=True)
	username = Column(String, unique=True, index=True, nullable=False)
	password_hash = Column(String, nullable=False)
	display_name = Column(String)
	created_at = Column(DateTime(timezone=True), server_default=func.now())


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=True)
    content_type = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    owner = relationship("User", backref="datasets")


class StatRecord(Base):
	__tablename__ = "stat_records"
	id = Column(Integer, primary_key=True)
	filename = Column(String, nullable=False)
	storage_path = Column(Text, nullable=False)
	size_bytes = Column(Integer, nullable=False)
	content_type = Column(String, default="text/csv")
	rows = Column(Integer)
	cols = Column(Integer)
	preview = Column(JSON) # first 5 rows as list of dicts
	created_at = Column(DateTime(timezone=True), server_default=func.now())
	owner_id = Column(Integer, ForeignKey("users.id"))
	owner = relationship("User")


class RainPoint(Base):
    __tablename__ = "rain_points"

    id         = Column(BigInteger, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)

    date       = Column(Date, nullable=True)       # วันที่ (YYYY-MM-DD) จากแกน time
    year       = Column(Integer, nullable=True)    # แยกปีออกมาเพื่อ query ง่าย
    province   = Column(String, nullable=False)    # จังหวัด (อังกฤษหรือไทย ตาม shapefile)
    district   = Column(String, nullable=False)    # อำเภอ
    lat        = Column(Float, nullable=False)
    lon        = Column(Float, nullable=False)
    rainfall_mm= Column(Float, nullable=True)

    dataset = relationship("Dataset", backref="rain_points")

# ดัชนีที่ช่วย query
Index("ix_rain_points_date", RainPoint.date)
Index("ix_rain_points_prov_dist", RainPoint.province, RainPoint.district)
Index("ix_rain_points_dataset_date", RainPoint.dataset_id, RainPoint.date)