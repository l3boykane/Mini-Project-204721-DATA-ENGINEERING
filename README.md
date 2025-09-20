# 🌍 Landslide Data Ingestion Platform

ระบบทดลอง **อัปโหลด วิเคราะห์ และจัดเก็บข้อมูลดินถล่ม**  
- Backend: [FastAPI](https://fastapi.tiangolo.com/) (JWT cookie auth, Upload `.nc`, `.csv/.xlsx`)  
- Frontend: [Next.js](https://nextjs.org/) + [Ant Design](https://ant.design/)  
- Database: PostgreSQL  
- Database UI: Adminer  

---

## 📂 Project structure

```
.
├── backend/        # FastAPI app (Python)
│   ├── app/
│   └── requirements.txt
├── frontend/       # Next.js app (TypeScript + Antd)
│   ├── app/
│   └── package.json
├── docker-compose.yaml
├── .env
└── README.md
```

---

## ⚙️ Requirements

- Docker & Docker Compose
- (optional) curl หรือ http client สำหรับทดสอบ API

---

## 🚀 Usage

### 1. Build & run
```bash
docker compose build
docker compose up -d
```

- Backend API → http://localhost:8000  
- Frontend (UI) → http://localhost:3000  
- Adminer (DB UI) → http://localhost:8080  

### 2. Register first user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin1234@##","display_name":"Admin"}'
```

### 3. Login & upload
1. เข้า http://localhost:3000/login → ใส่ username/password  
2. หน้า Home สามารถ:  
   - อัปโหลด `.nc` (NetCDF) → เก็บในตาราง `datasets`  
   - อัปโหลด `.csv/.xlsx` → เก็บในตาราง `stat_records`  
   - ดูข้อมูล preview จาก UI  

---

## 🛠️ Development workflow

- แก้โค้ด `backend/app/*.py` หรือ `frontend/app/*.tsx` แล้ว save → container reload อัตโนมัติ (เพราะ bind mount + watcher envs)  
- ถ้าแก้ไข dependencies (`requirements.txt`, `package.json`) → ต้อง `docker compose build` ใหม่  

---