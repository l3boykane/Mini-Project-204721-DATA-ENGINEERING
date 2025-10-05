# 🌍 Landslides in the northern region Platform

ระบบทดลอง **อัปโหลด วิเคราะห์ และจัดเก็บข้อมูลดินถล่มในภาคเหนือ**  
- Backend: [FastAPI](https://fastapi.tiangolo.com/) (JWT cookie auth, Upload `.nc`, `.xls/.xlsx`, `.dbf`)  
- Frontend: [Next.js](https://nextjs.org/) + [Ant Design](https://ant.design/)  
- Database: PostgreSQL  
- Database UI: Adminer  

---

## 📂 Project structure

```
.
├── backend/        # FastAPI app (Python)
│   ├── app/
│   ├── storage/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/       # Next.js app (TypeScript + Antd)
│   ├── app/
│   ├── public/
│   ├── styles/
│   ├── Dockerfile
│   ├── next-env.d.ts
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yaml
├── .env
├── .gitignore
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
docker compose build --no-cache
docker compose up -d
```

- Backend API → http://localhost:8000  
- Frontend (UI) → http://localhost:3000  
- Adminer (DB UI) → http://localhost:8080  

### 2. Register first user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin1234@##","full_name":"Administrator"}'
```


### 3. Init Data Province And District_name 
```bash
curl -X POST http://localhost:8000/init_data_province_district
```