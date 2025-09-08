#!/usr/bin/env python3
"""
สร้างไฟล์วิดีโอทดสอบด้วย Python
"""

import numpy as np
import cv2
import os

def create_test_video(filename="test_video.mp4", duration=30, fps=30, width=640, height=480):
    """สร้างไฟล์วิดีโอทดสอบ"""
    print(f"🎬 สร้างไฟล์วิดีโอทดสอบ: {filename}")
    print(f"⏱️ ความยาว: {duration} วินาที, {fps} FPS")
    print(f"📐 ขนาด: {width}x{height}")
    
    # สร้าง VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    # สร้างเฟรม
    total_frames = duration * fps
    
    for frame_num in range(total_frames):
        # สร้างภาพพื้นหลัง
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # คำนวณเวลา
        time_sec = frame_num / fps
        
        # สร้างข้อความ
        text = f"Test Video - {time_sec:.1f}s"
        
        # วาดข้อความ
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        color = (255, 255, 255)  # สีขาว
        thickness = 2
        
        # คำนวณตำแหน่งข้อความ
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (width - text_size[0]) // 2
        text_y = height // 2
        
        # วาดข้อความ
        cv2.putText(frame, text, (text_x, text_y), font, font_scale, color, thickness)
        
        # วาดกรอบ
        cv2.rectangle(frame, (50, 50), (width-50, height-50), (0, 255, 0), 3)
        
        # เพิ่มสีที่เปลี่ยนไปตามเวลา
        hue = int((frame_num / total_frames) * 180)
        color_hsv = np.array([[[hue, 255, 255]]], dtype=np.uint8)
        color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        
        # วาดวงกลมที่เปลี่ยนสี
        center_x = width // 2
        center_y = height // 2 + 100
        cv2.circle(frame, (center_x, center_y), 50, color_bgr.tolist(), -1)
        
        # เขียนเฟรม
        out.write(frame)
        
        # แสดงความคืบหน้า
        if frame_num % fps == 0:
            print(f"📹 สร้างเฟรม: {frame_num}/{total_frames} ({frame_num/total_frames*100:.1f}%)")
    
    # ปิดไฟล์
    out.release()
    
    print(f"✅ สร้างไฟล์วิดีโอเสร็จสิ้น: {filename}")
    
    # ตรวจสอบไฟล์
    if os.path.exists(filename):
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        print(f"📁 ขนาดไฟล์: {file_size:.2f} MB")
    else:
        print("❌ ไม่พบไฟล์ที่สร้าง")

if __name__ == "__main__":
    create_test_video() 