import uvicorn
from pathlib import Path
import os
import sys
import logging

# Setup logging ก่อน import app
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

if __name__ == "__main__":
    # สร้างโฟลเดอร์ที่จำเป็น
    Path("uploads").mkdir(exist_ok=True)
    Path("temp").mkdir(exist_ok=True)
    Path("storage").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)
    
    # ตรวจสอบว่าต้องการ debug mode หรือไม่
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    USE_DEBUGPY = os.getenv("USE_DEBUGPY", "false").lower() == "true"
    
    # ถ้าใช้ debugpy สำหรับ remote debugging
    if USE_DEBUGPY:
        try:
            import debugpy
            debugpy_port = int(os.getenv("DEBUGPY_PORT", "5678"))
            debugpy.listen(("0.0.0.0", debugpy_port))
            print(f"🐛 Debugpy listening on port {debugpy_port}")
            if os.getenv("DEBUGPY_WAIT", "false").lower() == "true":
                print("⏳ Waiting for debugger to attach...")
                debugpy.wait_for_client()
        except ImportError:
            print("⚠️  debugpy not installed. Install with: pip install debugpy")
        except Exception as e:
            print(f"⚠️  Failed to setup debugpy: {e}")
    
    # รันเซิร์ฟเวอร์
    # ⚠️  หมายเหตุ: Port 8001 ถูกใช้โดย RunPod Nginx/Proxy
    # ใช้ port 8010 ตาม RunPod HTTP Expose
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
        log_level="debug" if DEBUG else "info"
    ) 