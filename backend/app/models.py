from sqlalchemy import Column, Integer, String, DateTime, Date, Index, JSON, Text, ForeignKey, BigInteger, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from .database import Base


class User(Base):
	__tablename__ = "users"
	user_id       = Column(Integer, primary_key=True)
	username      = Column(String, unique=True, index=True, nullable=False)
	password_hash = Column(String, nullable=False)
	full_name     = Column(String)
	time_create   = Column(DateTime(timezone=True), server_default=func.now())

class UploadRainPoint(Base):
    __tablename__ = "upload_rain_point"
    upload_id     = Column(Integer, primary_key=True, index=True)
    filename      = Column(String, nullable=False)
    storage_path  = Column(String, nullable=False)
    size_bytes    = Column(BigInteger, nullable=True)
    content_type  = Column(String, nullable=True)
    time_create   = Column(DateTime(timezone=True), server_default=func.now())
    owner_id      = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    owner         = relationship("User", backref="upload_rain_point")

class Province(Base):
	__tablename__    = "province"
	province_id      = Column(Integer, primary_key=True)
	province_name    = Column(String, nullable=False)
	province_name_en = Column(String, nullable=False)
	time_create      = Column(DateTime(timezone=True), server_default=func.now())
	

class District(Base):
	__tablename__    = "district"
	district_id      = Column(Integer, primary_key=True)
	district_name    = Column(String, nullable=False)
	district_name_en = Column(String, nullable=False)
	province_id      = Column(Integer, ForeignKey("province.province_id", ondelete="CASCADE"), nullable=False)
	time_create      = Column(DateTime(timezone=True), server_default=func.now())
	province         = relationship("Province", backref=backref("districts", cascade="all, delete-orphan"), passive_deletes=True)
	
	
class RainPoint(Base):
    __tablename__     = "rain_points"
    pk_id             = Column(BigInteger, primary_key=True, index=True)
    upload_id         = Column(Integer, ForeignKey("upload_rain_point.upload_id", ondelete="CASCADE"), nullable=False, index=True)
    date              = Column(Date, nullable=True) # วันที่ (YYYY-MM-DD) จากแกน time
    year              = Column(Integer, nullable=True)   
    province_id       = Column(Integer, ForeignKey("province.province_id", ondelete="CASCADE"), nullable=False, index=True)    
    district_id       = Column(Integer, ForeignKey("district.district_id", ondelete="CASCADE"), nullable=False, index=True)
    rain_mm_wmean     = Column(Float, nullable=True)
    rainfall_mm       = Column(Float, nullable=True)
    district          = relationship("District", backref=backref("districts", cascade="all, delete-orphan"), passive_deletes=True)
    province          = relationship("Province", backref=backref("province", cascade="all, delete-orphan"), passive_deletes=True)
	
class UploadRisk(Base):
    __tablename__ = "upload_risk"
    upload_risk_id     = Column(Integer, primary_key=True, index=True)
    filename      = Column(String, nullable=False)
    storage_path  = Column(String, nullable=False)
    size_bytes    = Column(BigInteger, nullable=True)
    content_type  = Column(String, nullable=True)
    time_create   = Column(DateTime(timezone=True), server_default=func.now())
    owner_id      = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    owner         = relationship("User", backref="upload_risk")

class RiskPoint(Base):
    __tablename__     = "risk_points"
    risk_id           = Column(BigInteger, primary_key=True, index=True)
    upload_risk_id    = Column(Integer, ForeignKey("upload_risk.upload_risk_id", ondelete="CASCADE"), nullable=False, index=True)
    province_id       = Column(Integer, ForeignKey("province.province_id", ondelete="CASCADE"), nullable=False, index=True)    
    district_id       = Column(Integer, ForeignKey("district.district_id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level        = Column(Integer, nullable=True)
    district          = relationship("District", backref=backref("risk_points", cascade="all, delete-orphan"), passive_deletes=True)
    province          = relationship("Province", backref=backref("risk_points", cascade="all, delete-orphan"), passive_deletes=True)

# ดัชนีที่ช่วย query
Index("ix_rain_points_date", RainPoint.date)
Index("ix_rain_points_year", RainPoint.year)
Index("ix_province_name", Province.province_name)
Index("ix_province_name_en", Province.province_name_en)
Index("ix_district_province", District.province_id)
Index("ix_district_name", District.district_name)
Index("ix_district_name_en", District.district_name_en)