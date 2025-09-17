import uvicorn
from pathlib import Path

if __name__ == "__main__":
    # สร้างโฟลเดอร์ที่จำเป็น
    Path("uploads").mkdir(exist_ok=True)
    Path("temp").mkdir(exist_ok=True)
    Path("storage").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)
    
    # รันเซิร์ฟเวอร์
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    ) 