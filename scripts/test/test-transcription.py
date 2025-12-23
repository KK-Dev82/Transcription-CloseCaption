import requests
import json
import time
import subprocess
from datetime import datetime

API_URL = "http://localhost:8010"
VIDEO_URL = "https://korrakang.com/video/v30-1.mp4"
VIDEO_DURATION = 1800  # 30 minutes

print("=" * 70)
print("🧪 Testing Transcription with SQLite Streaming")
print("=" * 70)
print(f"Video URL: {VIDEO_URL}")
print(f"Video Duration: {VIDEO_DURATION} seconds (30 minutes)")
print()

# Check initial RAM
ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
ram_lines = ram_result.stdout.split('\n')
if len(ram_lines) >= 2:
    mem_line = ram_lines[1].split()
    if len(mem_line) >= 3:
        used_gb = float(mem_line[2]) / 1024
        total_gb = float(mem_line[1]) / 1024
        ram_pct = (float(mem_line[2]) / float(mem_line[1])) * 100
        print(f"📊 Initial RAM: {used_gb:.1f}GB/{total_gb:.1f}GB ({ram_pct:.1f}%)")
        print()

# Send request
print("📤 Sending transcription request...")
start_time = time.time()

try:
    response = requests.post(
        f"{API_URL}/api/transcribe/",
        json={
            "file_url": VIDEO_URL,
            "language": "th",
            "model_size": "base"
        },
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        task_id = result.get('task_id')
        print(f"✅ Request sent successfully")
        print(f"   Task ID: {task_id}")
        print()
        
        # Monitor task and RAM
        print("=" * 70)
        print("📊 Monitoring Task Progress & RAM Usage")
        print("=" * 70)
        print()
        
        max_wait = 600  # 10 minutes
        check_interval = 10
        last_status = None
        last_progress = None
        max_ram_used = used_gb
        max_cpu_worker_ram = 0
        
        while True:
            try:
                # Check task status
                response = requests.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    progress = data.get('progress', 0)
                    
                    # Check RAM usage
                    ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
                    ram_lines = ram_result.stdout.split('\n')
                    if len(ram_lines) >= 2:
                        mem_line = ram_lines[1].split()
                        if len(mem_line) >= 3:
                            used_gb = float(mem_line[2]) / 1024
                            ram_pct = (float(mem_line[2]) / float(mem_line[1])) * 100
                            max_ram_used = max(max_ram_used, used_gb)
                    
                    # Check CPU worker RAM
                    ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                    for line in ps_result.stdout.split('\n'):
                        if 'rq worker' in line and 'cpu' in line.lower():
                            parts = line.split()
                            if len(parts) >= 6:
                                rss_mb = float(parts[5]) / 1024
                                max_cpu_worker_ram = max(max_cpu_worker_ram, rss_mb)
                    
                    # Get detailed stage info
                    current_stage = data.get('current_stage', 'unknown')
                    stage_description = data.get('current_stage_description', '')
                    completed_chunks = data.get('completed_chunks', 0)
                    total_chunks = data.get('total_chunks', 0)
                    
                    # Print status change with detailed phase info
                    last_stage = getattr(last_status, 'stage', None) if isinstance(last_status, object) and hasattr(last_status, 'stage') else None
                    status_changed = (status, progress, current_stage) != (last_status, last_progress, last_stage)
                    if status_changed:
                        elapsed = time.time() - start_time
                        stage_info = ""
                        if current_stage and current_stage != 'unknown':
                            stage_info = f" | Stage: {current_stage}"
                        if stage_description:
                            stage_info += f" ({stage_description})"
                        if total_chunks > 0:
                            stage_info += f" | Chunks: {completed_chunks}/{total_chunks}"
                        
                        print(f"[{elapsed:.0f}s] Status: {status}, Progress: {progress}%, RAM: {used_gb:.1f}GB ({ram_pct:.1f}%), CPU Worker: {max_cpu_worker_ram:.1f}MB{stage_info}")
                        last_status = type('Status', (), {'status': status, 'stage': current_stage})()
                        last_progress = progress
                    
                    if status == 'completed':
                        end_time = time.time()
                        total_time = end_time - start_time
                        
                        print()
                        print("=" * 70)
                        print("✅ Task Completed")
                        print("=" * 70)
                        print()
                        
                        transcription = data.get('transcription', {})
                        text = transcription.get('text', '')
                        processing_time = data.get('processing_time', 0)
                        
                        print(f"Task ID: {task_id[:16]}...")
                        print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
                        if processing_time:
                            speedup = VIDEO_DURATION / processing_time if processing_time > 0 else 0
                            print(f"Processing time: {processing_time:.2f} seconds ({processing_time/60:.2f} minutes)")
                            print(f"Speedup: {speedup:.2f}× realtime")
                        print()
                        
                        # Show phase timings with detailed breakdown
                        phase_timings = data.get('phase_timings', {})
                        if phase_timings:
                            print("📊 Phase Timings (Detailed Breakdown):")
                            print()
                            
                            # Preprocess timings
                            if isinstance(phase_timings, dict):
                                # Download phase
                                download_time = phase_timings.get('download_time', 0)
                                if download_time:
                                    print("1️⃣  Download Phase:")
                                    print(f"   ✅ Download video: {download_time:.2f}s")
                                    print()
                                
                                # Audio extraction phase
                                extract_time = phase_timings.get('extract_time', 0)
                                if extract_time:
                                    print("2️⃣  Audio Extraction Phase:")
                                    print(f"   ✅ Extract audio: {extract_time:.2f}s")
                                    print()
                                
                                # Chunking phase
                                chunk_time = phase_timings.get('chunk_time', 0)
                                if chunk_time:
                                    print("3️⃣  Chunking Phase:")
                                    print(f"   ✅ Create chunks: {chunk_time:.2f}s")
                                    print()
                                
                                # Enqueue phase
                                enqueue_time = phase_timings.get('enqueue_time', 0)
                                if enqueue_time:
                                    print("4️⃣  Enqueue Phase:")
                                    print(f"   ✅ Enqueue chunks: {enqueue_time:.2f}s")
                                    print()
                                
                                total_preprocess = phase_timings.get('total_preprocess_time', 0)
                                if total_preprocess:
                                    print("📊 Total Preprocess Time:")
                                    print(f"   ✅ {total_preprocess:.2f}s")
                                    print()
                                
                                # Transcription phase (from chunks)
                                transcription_time = phase_timings.get('transcription_time', 0)
                                if transcription_time:
                                    print("5️⃣  Transcription Phase:")
                                    print(f"   ✅ Transcribe chunks: {transcription_time:.2f}s")
                                    print()
                                
                                # Aggregator timings
                                aggregator = phase_timings.get('aggregator', {})
                                if aggregator:
                                    print("6️⃣  Aggregator Phase (SQLite Streaming):")
                                    wait_time = aggregator.get('wait_chunks_time', 0)
                                    fetch_time = aggregator.get('fetch_chunks_time', 0)
                                    merge_time = aggregator.get('merge_time', 0)
                                    thai_time = aggregator.get('thai_processing_time', 0)
                                    total_agg = aggregator.get('total_aggregator_time', 0)
                                    
                                    if wait_time:
                                        print(f"   ✅ Wait chunks: {wait_time:.2f}s")
                                    if fetch_time:
                                        print(f"   ✅ Fetch chunks: {fetch_time:.2f}s")
                                    if merge_time:
                                        print(f"   ✅ Merge: {merge_time:.2f}s")
                                    if thai_time:
                                        print(f"   ✅ Thai processing: {thai_time:.2f}s")
                                    if total_agg:
                                        print(f"   ✅ Total aggregator: {total_agg:.2f}s")
                                    print()
                                
                                total_e2e = aggregator.get('total_end_to_end_time', 0) if aggregator else phase_timings.get('total_end_to_end_time', 0)
                                if total_e2e:
                                    print("🎯 Total End-to-End Time:")
                                    print(f"   ✅ {total_e2e:.2f}s ({total_e2e/60:.2f} minutes)")
                                    print()
                        
                        # Final RAM check
                        ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
                        ram_lines = ram_result.stdout.split('\n')
                        if len(ram_lines) >= 2:
                            mem_line = ram_lines[1].split()
                            if len(mem_line) >= 3:
                                used_gb = float(mem_line[2]) / 1024
                                ram_pct = (float(mem_line[2]) / float(mem_line[1])) * 100
                                print(f"📊 RAM Usage:")
                                print(f"   Initial: {used_gb:.1f}GB")
                                print(f"   Peak: {max_ram_used:.1f}GB")
                                print(f"   Final: {used_gb:.1f}GB ({ram_pct:.1f}%)")
                                print(f"   CPU Worker Peak: {max_cpu_worker_ram:.1f}MB")
                                if max_ram_used < 5:
                                    print(f"   ✅ RAM usage is healthy (peak < 5GB)")
                                elif max_ram_used < 10:
                                    print(f"   ⚠️  RAM usage is moderate (peak 5-10GB)")
                                else:
                                    print(f"   ❌ RAM usage is high (peak > 10GB)")
                                if max_cpu_worker_ram < 1000:
                                    print(f"   ✅ CPU Worker RAM is excellent (peak < 1GB)")
                                elif max_cpu_worker_ram < 2000:
                                    print(f"   ✅ CPU Worker RAM is good (peak < 2GB)")
                                else:
                                    print(f"   ⚠️  CPU Worker RAM is high (peak > 2GB)")
                                print()
                        
                        if text:
                            print(f"Transcription ({len(text)} characters):")
                            print("-" * 70)
                            print(text[:500] + "..." if len(text) > 500 else text)
                            print("-" * 70)
                        else:
                            print("⚠️  No transcription text found")
                        
                        break
                    elif status in ['failed', 'error']:
                        print(f"❌ Task failed: {data.get('error', 'Unknown error')}")
                        break
            except Exception as e:
                print(f"⚠️  Error checking status: {e}")
            
            if time.time() - start_time > max_wait:
                print("⏰ Timeout waiting for task completion")
                break
            
            time.sleep(check_interval)
    else:
        print(f"❌ Request failed: {response.status_code} - {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()