"""
AcademicAgent Backend — FastAPI 入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AcademicAgent API",
    description="SCI论文多Agent写作系统后端",
    version="0.1.0",
)

# CORS — 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}
