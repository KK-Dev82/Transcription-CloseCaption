# 1. Tail GPU 0 Log (real-time)
tail -f /tmp/rq-worker-gpu0.log

# 2. Tail GPU 1 Log (real-time)
tail -f /tmp/rq-worker-gpu1.log

# 3. Tail ทั้ง 2 GPU พร้อมกัน
tail -f /tmp/rq-worker-gpu*.log

# 4. ดู Logs ล่าสุด 50 บรรทัด
tail -50 /tmp/rq-worker-gpu0.log

# 5. ดู Logs และ Filter (ดูเฉพาะ model/GPU/CUDA)
tail -100 /tmp/rq-worker-gpu0.log | grep -E 'model|Model|GPU|CUDA|cuda|device|Device|loading|Loading|Warming|warmup|ERROR|Error|error'