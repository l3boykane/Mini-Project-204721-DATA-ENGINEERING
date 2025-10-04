from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import datetime as dt

class UserOut(BaseModel):
	user_id: int
	username: str
	full_name: Optional[str]
	class Config:
		orm_mode = True


class RegisterIn(BaseModel):
	username: str
	password: str
	full_name: Optional[str] = None


class LoginIn(BaseModel):
	username: str
	password: str

class RainPointOut(BaseModel):
    id: int
    date: dt.date
    rain_mm_wmean: float | None = None
    province_id: int
    district_id: int
    province_name: str
    district_name: str
    province_name_en: str
    district_name_en: str
    class Config:
        from_attributes = True
class ListPaginationOut(BaseModel):
    page: int
    page_size: int
    total: int
    all_page: int
    items: List[RainPointOut]
    
class ProvinceDistrictPointOut(BaseModel):
    province_id: int
    district_id: int
    province_name: str
    district_name: str
    province_name_en: str
    district_name_en: str

class ListProvinceDistrictPaginationOut(BaseModel):
    page: int
    page_size: int
    total: int
    all_page: int
    items: List[ProvinceDistrictPointOut]



class ProvinceOut(BaseModel):
    province_id: int
    province_name: str
    province_name_en: str
    class Config:
        from_attributes = True
class ProvinceListOut(BaseModel):
    total: int
    items: list[ProvinceOut]

class DistrictOut(BaseModel):
    district_id: int
    district_name: str
    district_name_en: str
    class Config:
        from_attributes = True
        
class DistrictListOut(BaseModel):
    total: int
    items: list[DistrictOut]

class RiskPointOut(BaseModel):
    id: int
    risk_level: int | None = None
    province_id: int
    district_id: int
    province_name: str
    district_name: str
    province_name_en: str
    district_name_en: str
    class Config:
        from_attributes = True

class ListRiskPaginationOut(BaseModel):
    page: int
    page_size: int
    total: int
    all_page: int
    items: List[RiskPointOut]

class IncidentStatisticsPointOut(BaseModel):
    id: int
    disaster_date: dt.date
    count_of_disasters: int
    province_id: int
    district_id: int
    province_name: str
    district_name: str
    province_name_en: str
    district_name_en: str
    class Config:
        from_attributes = True

class ListIncidentStatisticsPaginationOut(BaseModel):
    page: int
    page_size: int
    total: int
    all_page: int
    items: List[IncidentStatisticsPointOut]

class DateLimitOut(BaseModel):
    min_date: dt.date
    max_date: dt.date



class GraphPointOut(BaseModel):
    date: dt.date
    rain_mm_wmean: float | None = None
    province_id: int
    district_id: int
    province_name: str
    district_name: str
    province_name_en: str
    district_name_en: str
    risk_level: int
    count_of_disasters: int
    class Config:
        from_attributes = True
class ListGraphOut(BaseModel):
    items: List[GraphPointOut]