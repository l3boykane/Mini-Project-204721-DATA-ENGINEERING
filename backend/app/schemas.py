from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class UserOut(BaseModel):
	id: int
	username: str
	display_name: Optional[str]
	class Config:
		orm_mode = True


class RegisterIn(BaseModel):
	username: str
	password: str
	display_name: Optional[str] = None


class LoginIn(BaseModel):
	username: str
	password: str


class DatasetOut(BaseModel):
	id: int
	filename: str
	size_bytes: int
	content_type: str
	dims: Optional[Dict[str, int]]
	vars: Optional[List[Dict[str, Any]]]
	time_coverage_start: Optional[str]
	time_coverage_end: Optional[str]
	bbox: Optional[Dict[str, float]]
	note: Optional[str]
	created_at: Optional[str]
	class Config:
		orm_mode = True


class StatRecordOut(BaseModel):
	id: int
	filename: str
	size_bytes: int
	content_type: str
	rows: int
	cols: int
	preview: Optional[List[Dict[str, Any]]]
	created_at: Optional[str]
	class Config:
		orm_mode = True