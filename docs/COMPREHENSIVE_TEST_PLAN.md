# 🧪 Comprehensive Test Plan: Status Messages & Estimated Time Remaining

**วันที่สร้าง**: 2024-12-05  
**Purpose**: ออกแบบ Test Case สำหรับการปรับปรุง Status Messages และ Estimated Time Remaining

---

## 📋 สารบัญ

1. [Test Strategy](#test-strategy)
2. [Test Levels](#test-levels)
3. [Manual Test Cases](#manual-test-cases)
4. [Automated Test Cases](#automated-test-cases)
5. [Test Tools & Frameworks](#test-tools--frameworks)
6. [Test Execution Plan](#test-execution-plan)

---

## 🎯 Test Strategy

### Hybrid Approach: Manual + Automated

**Manual Testing (30%):**
- ✅ User Experience Testing
- ✅ Edge Cases Testing
- ✅ Integration Testing

**Automated Testing (70%):**
- ✅ Unit Tests (Status Messages Logic)
- ✅ Integration Tests (API Endpoints)
- ✅ Performance Tests (Estimated Time Accuracy)
- ✅ Regression Tests

---

## 📊 Test Levels

### 1. Unit Tests (Automated)

**Scope:**
- Status Messages Generation
- Estimated Time Calculation Logic
- Progress Tracking Updates

**Tools:**
- `pytest` (Python Testing Framework)
- `unittest` (Built-in Python Testing)

### 2. Integration Tests (Automated)

**Scope:**
- API Endpoints Response
- Worker Status Updates
- Progress Tracking Flow

**Tools:**
- `pytest` + `httpx` (API Testing)
- `pytest-asyncio` (Async Testing)

### 3. End-to-End Tests (Manual + Automated)

**Scope:**
- Full Transcription Flow
- Status Updates During Processing
- Estimated Time Accuracy

**Tools:**
- `pytest` (Automated E2E)
- Manual Testing (User Experience)

### 4. Performance Tests (Automated)

**Scope:**
- Estimated Time Accuracy
- Status Update Frequency
- Response Time

**Tools:**
- `pytest-benchmark` (Performance Testing)
- Custom Performance Metrics

---

## 📝 Manual Test Cases

### TC-1: Status Messages - Audio Extraction

**Objective:** ตรวจสอบ Status Messages ระหว่าง Audio Extraction

**Steps:**
1. ส่ง transcription request (video file)
2. Monitor progress endpoint: `GET /progress/transcription/{task_id}`
3. ตรวจสอบ response fields:
   - `current_stage` = `"extracting_audio"`
   - `current_stage_description` = `"กำลังแยกเสียงจากวิดีโอ"`
   - `stage_progress` = 0-100

**Expected Results:**
- ✅ `current_stage` แสดง `"extracting_audio"` ระหว่าง extraction
- ✅ `current_stage_description` มีข้อความที่ชัดเจน
- ✅ `stage_progress` เพิ่มขึ้นจาก 0 ถึง 100

**Test Data:**
- Video file: 1 minute, 5 minutes, 30 minutes

---

### TC-2: Status Messages - Transcription (Non-Chunking)

**Objective:** ตรวจสอบ Status Messages ระหว่าง Transcription (Non-Chunking)

**Steps:**
1. ส่ง transcription request (audio file, `use_chunking=false`)
2. Monitor progress endpoint
3. ตรวจสอบ response fields:
   - `current_stage` = `"transcribing"`
   - `current_stage_description` = `"กำลังแปลงเสียงเป็นข้อความ"`
   - `stage_progress` = 0-100

**Expected Results:**
- ✅ `current_stage` แสดง `"transcribing"` ระหว่าง transcription
- ✅ `current_stage_description` มีข้อความที่ชัดเจน
- ✅ `stage_progress` เพิ่มขึ้นจาก 0 ถึง 100

---

### TC-3: Status Messages - Transcription (Chunking)

**Objective:** ตรวจสอบ Status Messages ระหว่าง Transcription (Chunking)

**Steps:**
1. ส่ง transcription request (video file, `use_chunking=true`, `chunk_duration=30`)
2. Monitor progress endpoint
3. ตรวจสอบ response fields:
   - `current_stage` = `"transcribing"`
   - `current_stage_description` = `"กำลังแปลงเสียง chunk X/Y"`
   - `completed_chunks` / `total_chunks`

**Expected Results:**
- ✅ `current_stage` แสดง `"transcribing"` ระหว่าง transcription
- ✅ `current_stage_description` แสดง chunk number (เช่น "กำลังแปลงเสียง chunk 5/10")
- ✅ `completed_chunks` เพิ่มขึ้นเมื่อแต่ละ chunk เสร็จ

---

### TC-4: Estimated Time Remaining - Non-Chunking

**Objective:** ตรวจสอบ Estimated Time Remaining (Non-Chunking)

**Steps:**
1. ส่ง transcription request (audio file, `use_chunking=false`)
2. Monitor progress endpoint ทุก 5 วินาที
3. ตรวจสอบ response fields:
   - `estimated_remaining_seconds`
   - `estimated_remaining_formatted`
   - `elapsed_seconds`

**Expected Results:**
- ✅ `estimated_remaining_seconds` คำนวณจาก progress และ elapsed time
- ✅ `estimated_remaining_formatted` แสดงเป็นรูปแบบ "M:SS"
- ✅ Estimated time ลดลงเมื่อ progress เพิ่มขึ้น

**Validation:**
- บันทึก estimated time ในแต่ละช่วง
- เปรียบเทียบกับ actual remaining time
- Error margin: ±20% (ยอมรับได้)

---

### TC-5: Estimated Time Remaining - Chunking

**Objective:** ตรวจสอบ Estimated Time Remaining (Chunking)

**Steps:**
1. ส่ง transcription request (video file, `use_chunking=true`, `chunk_duration=30`)
2. Monitor progress endpoint ทุก 5 วินาที
3. ตรวจสอบ response fields:
   - `estimated_remaining_seconds`
   - `average_chunk_time`
   - `completed_chunks` / `total_chunks`

**Expected Results:**
- ✅ `estimated_remaining_seconds` คำนวณจาก chunks ที่เหลือ (ถ้า `completed_chunks >= 2`)
- ✅ `average_chunk_time` แสดงเวลาเฉลี่ยต่อ chunk
- ✅ Estimated time ลดลงเมื่อ chunks เสร็จมากขึ้น

**Validation:**
- บันทึก estimated time เมื่อ `completed_chunks = 2, 5, 10, ...`
- เปรียบเทียบกับ actual remaining time
- Error margin: ±15% (ดีกว่า non-chunking เพราะคำนวณจาก chunks)

---

### TC-6: Edge Cases - Very Short Video

**Objective:** ตรวจสอบ Edge Case: วีดีโอสั้นมาก (< 10 วินาที)

**Steps:**
1. ส่ง transcription request (video file: 5 seconds)
2. Monitor progress endpoint
3. ตรวจสอบ status messages และ estimated time

**Expected Results:**
- ✅ Status messages แสดงถูกต้อง
- ✅ Estimated time ไม่แสดงค่าที่ผิดปกติ (เช่น negative หรือมากเกินไป)
- ✅ Progress ทำงานได้ปกติ

---

### TC-7: Edge Cases - Very Long Video

**Objective:** ตรวจสอบ Edge Case: วีดีโอยาวมาก (> 2 ชั่วโมง)

**Steps:**
1. ส่ง transcription request (video file: 2 hours, `use_chunking=true`)
2. Monitor progress endpoint
3. ตรวจสอบ estimated time accuracy

**Expected Results:**
- ✅ Estimated time คำนวณได้ถูกต้อง
- ✅ Status messages แสดง chunk progress ได้ถูกต้อง
- ✅ ไม่มี memory leak หรือ performance issues

---

### TC-8: Edge Cases - First Chunk

**Objective:** ตรวจสอบ Edge Case: Chunk แรก (ยังไม่มีข้อมูลสำหรับ average)

**Steps:**
1. ส่ง transcription request (video file, `use_chunking=true`)
2. Monitor progress endpoint เมื่อ `completed_chunks = 0, 1`
3. ตรวจสอบ estimated time calculation

**Expected Results:**
- ✅ เมื่อ `completed_chunks = 0`: ใช้ progress percentage calculation (fallback)
- ✅ เมื่อ `completed_chunks = 1`: ใช้ progress percentage หรือ chunk time (fallback)
- ✅ เมื่อ `completed_chunks >= 2`: ใช้ chunk-based calculation

---

### TC-9: User Experience - Real-time Updates

**Objective:** ตรวจสอบ User Experience: Real-time Status Updates

**Steps:**
1. ส่ง transcription request
2. เปิด Frontend UI (หรือใช้ polling script)
3. ตรวจสอบว่า status updates แสดงแบบ real-time

**Expected Results:**
- ✅ Status messages อัปเดตแบบ real-time (ทุก 1-2 วินาที)
- ✅ Progress bar อัปเดต smooth
- ✅ Estimated time อัปเดตตาม progress

**Tools:**
- Frontend UI (Manual)
- Polling script (Automated)

---

### TC-10: Error Handling - Failed Transcription

**Objective:** ตรวจสอบ Error Handling เมื่อ Transcription ล้มเหลว

**Steps:**
1. ส่ง transcription request (invalid file หรือ file ที่เสียหาย)
2. Monitor progress endpoint
3. ตรวจสอบ status messages เมื่อเกิด error

**Expected Results:**
- ✅ `status` = `"failed"`
- ✅ `current_stage` = `"error"` หรือ `null`
- ✅ `error_message` มีข้อความที่ชัดเจน
- ✅ Estimated time ไม่แสดง (หรือแสดง 0)

---

## 🤖 Automated Test Cases

### AT-1: Unit Test - Status Messages Generation

**File:** `tests/unit/test_status_messages.py`

```python
import pytest
from app.api.progress import get_transcription_progress

@pytest.mark.asyncio
async def test_status_message_audio_extraction():
    """Test status message for audio extraction stage"""
    # Mock task data
    task_data = {
        "status": "processing",
        "current_stage": "extracting_audio",
        "current_stage_description": "กำลังแยกเสียงจากวิดีโอ",
        "stage_progress": 50
    }
    
    # Test
    response = await get_transcription_progress("test-task-id")
    
    # Assert
    assert response["current_stage"] == "extracting_audio"
    assert "แยกเสียง" in response["current_stage_description"]
    assert response["stage_progress"] == 50

@pytest.mark.asyncio
async def test_status_message_transcribing():
    """Test status message for transcribing stage"""
    task_data = {
        "status": "processing",
        "current_stage": "transcribing",
        "current_stage_description": "กำลังแปลงเสียง chunk 5/10",
        "completed_chunks": 5,
        "total_chunks": 10
    }
    
    response = await get_transcription_progress("test-task-id")
    
    assert response["current_stage"] == "transcribing"
    assert "แปลงเสียง" in response["current_stage_description"]
    assert "5/10" in response["current_stage_description"]
```

---

### AT-2: Unit Test - Estimated Time Calculation

**File:** `tests/unit/test_estimated_time.py`

```python
import pytest
from app.api.progress import calculate_estimated_remaining

def test_estimated_time_from_progress():
    """Test estimated time calculation from progress percentage"""
    task_data = {
        "progress": 50,
        "elapsed_seconds": 60
    }
    
    estimated = calculate_estimated_remaining(task_data)
    
    # Should be: 60 / 0.5 - 60 = 60 seconds
    assert estimated["estimated_remaining_seconds"] == 60

def test_estimated_time_from_chunks():
    """Test estimated time calculation from chunks"""
    task_data = {
        "completed_chunks": 5,
        "total_chunks": 10,
        "elapsed_seconds": 50,
        "task_breakdown": [
            {"type": "transcription_chunk", "time": 10},
            {"type": "transcription_chunk", "time": 10},
            {"type": "transcription_chunk", "time": 10},
            {"type": "transcription_chunk", "time": 10},
            {"type": "transcription_chunk", "time": 10}
        ]
    }
    
    estimated = calculate_estimated_remaining(task_data)
    
    # Average: 10 seconds per chunk
    # Remaining: 5 chunks * 10 = 50 seconds
    assert estimated["estimated_remaining_seconds"] == 50
    assert estimated["average_chunk_time"] == 10

def test_estimated_time_fallback():
    """Test fallback to progress calculation when chunks < 2"""
    task_data = {
        "completed_chunks": 1,
        "total_chunks": 10,
        "progress": 10,
        "elapsed_seconds": 10
    }
    
    estimated = calculate_estimated_remaining(task_data)
    
    # Should fallback to progress calculation
    assert "estimated_remaining_seconds" in estimated
```

---

### AT-3: Integration Test - Progress Endpoint

**File:** `tests/integration/test_progress_endpoint.py`

```python
import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_progress_endpoint_status_messages():
    """Test progress endpoint returns status messages"""
    # Start transcription (mock)
    response = client.post("/transcribe/", json={
        "file_url": "http://example.com/test.mp4",
        "language": "th",
        "model_size": "base"
    })
    task_id = response.json()["task_id"]
    
    # Get progress
    progress_response = client.get(f"/progress/transcription/{task_id}")
    
    assert progress_response.status_code == 200
    data = progress_response.json()
    
    # Check status messages
    assert "current_stage" in data
    assert "current_stage_description" in data
    assert "stage_progress" in data or data.get("current_stage") is None

def test_progress_endpoint_estimated_time():
    """Test progress endpoint returns estimated time"""
    # Start transcription (mock)
    task_id = "test-task-id"
    
    # Get progress
    progress_response = client.get(f"/progress/transcription/{task_id}")
    
    assert progress_response.status_code == 200
    data = progress_response.json()
    
    # Check estimated time
    if data.get("progress", 0) > 0 and data.get("progress", 100) < 100:
        assert "estimated_remaining_seconds" in data
        assert "estimated_remaining_formatted" in data
```

---

### AT-4: Performance Test - Estimated Time Accuracy

**File:** `tests/performance/test_estimated_time_accuracy.py`

```python
import pytest
import time
from app.api.progress import calculate_estimated_remaining

@pytest.mark.benchmark
def test_estimated_time_accuracy_chunking(benchmark):
    """Test estimated time accuracy for chunking mode"""
    
    # Simulate transcription with chunks
    task_data = {
        "completed_chunks": 5,
        "total_chunks": 10,
        "elapsed_seconds": 50,
        "task_breakdown": [
            {"type": "transcription_chunk", "time": 10} for _ in range(5)
        ]
    }
    
    # Calculate estimated time
    estimated = benchmark(calculate_estimated_remaining, task_data)
    
    # Validate accuracy (should be within 15% margin)
    actual_remaining = 50  # 5 chunks * 10 seconds
    error_margin = abs(estimated["estimated_remaining_seconds"] - actual_remaining) / actual_remaining
    
    assert error_margin <= 0.15, f"Error margin too high: {error_margin * 100}%"

@pytest.mark.benchmark
def test_estimated_time_accuracy_non_chunking(benchmark):
    """Test estimated time accuracy for non-chunking mode"""
    
    task_data = {
        "progress": 50,
        "elapsed_seconds": 60
    }
    
    estimated = benchmark(calculate_estimated_remaining, task_data)
    
    # Validate accuracy (should be within 20% margin)
    actual_remaining = 60
    error_margin = abs(estimated["estimated_remaining_seconds"] - actual_remaining) / actual_remaining
    
    assert error_margin <= 0.20, f"Error margin too high: {error_margin * 100}%"
```

---

### AT-5: E2E Test - Full Transcription Flow

**File:** `tests/e2e/test_transcription_flow.py`

```python
import pytest
import asyncio
import httpx

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_transcription_flow_with_status_messages():
    """Test full transcription flow with status messages"""
    
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        # Step 1: Start transcription
        response = await client.post(f"{base_url}/transcribe/", json={
            "file_url": "http://example.com/test.mp4",
            "language": "th",
            "model_size": "base",
            "use_chunking": True,
            "chunk_duration": 30
        })
        task_id = response.json()["task_id"]
        
        # Step 2: Monitor progress
        stages_seen = []
        estimated_times = []
        
        for _ in range(20):  # Monitor for 20 iterations
            progress_response = await client.get(f"{base_url}/progress/transcription/{task_id}")
            data = progress_response.json()
            
            current_stage = data.get("current_stage")
            if current_stage and current_stage not in stages_seen:
                stages_seen.append(current_stage)
            
            if "estimated_remaining_seconds" in data:
                estimated_times.append(data["estimated_remaining_seconds"])
            
            if data.get("status") == "completed":
                break
            
            await asyncio.sleep(2)
        
        # Assertions
        assert "extracting_audio" in stages_seen or "transcribing" in stages_seen
        assert len(estimated_times) > 0
        
        # Estimated time should decrease over time
        if len(estimated_times) >= 2:
            assert estimated_times[-1] <= estimated_times[0] or data.get("status") == "completed"
```

---

## 🛠️ Test Tools & Frameworks

### 1. Python Testing Framework

**Primary:**
- ✅ `pytest` - Modern Python testing framework
- ✅ `pytest-asyncio` - Async testing support
- ✅ `pytest-benchmark` - Performance testing
- ✅ `pytest-cov` - Code coverage

**Installation:**
```bash
pip install pytest pytest-asyncio pytest-benchmark pytest-cov httpx
```

### 2. API Testing

**Tools:**
- ✅ `httpx` - Async HTTP client (for FastAPI testing)
- ✅ `TestClient` - FastAPI built-in test client

### 3. Mocking

**Tools:**
- ✅ `unittest.mock` - Built-in Python mocking
- ✅ `pytest-mock` - Pytest mocking plugin

### 4. Test Data Management

**Tools:**
- ✅ `pytest-fixtures` - Test data fixtures
- ✅ `faker` - Generate fake test data

### 5. Continuous Integration

**Tools:**
- ✅ GitHub Actions / GitLab CI
- ✅ `pytest-xdist` - Parallel test execution

---

## 📅 Test Execution Plan

### Phase 1: Unit Tests (Week 1)

**Duration:** 3-5 days

**Tasks:**
- ✅ สร้าง unit tests สำหรับ Status Messages Logic
- ✅ สร้าง unit tests สำหรับ Estimated Time Calculation
- ✅ Run tests และ fix bugs

**Deliverables:**
- Unit test files
- Test coverage report (target: 80%+)

---

### Phase 2: Integration Tests (Week 1-2)

**Duration:** 5-7 days

**Tasks:**
- ✅ สร้าง integration tests สำหรับ API endpoints
- ✅ สร้าง integration tests สำหรับ Worker updates
- ✅ Run tests และ fix bugs

**Deliverables:**
- Integration test files
- Test results report

---

### Phase 3: Manual Testing (Week 2)

**Duration:** 3-5 days

**Tasks:**
- ✅ Execute manual test cases (TC-1 to TC-10)
- ✅ Document test results
- ✅ Report bugs และ issues

**Deliverables:**
- Manual test results document
- Bug reports

---

### Phase 4: Performance Testing (Week 2-3)

**Duration:** 3-5 days

**Tasks:**
- ✅ Run performance tests
- ✅ Validate Estimated Time accuracy
- ✅ Optimize if needed

**Deliverables:**
- Performance test results
- Accuracy analysis report

---

### Phase 5: E2E Testing (Week 3)

**Duration:** 3-5 days

**Tasks:**
- ✅ Run E2E tests
- ✅ Test with real video files
- ✅ Validate full flow

**Deliverables:**
- E2E test results
- Final validation report

---

## 📊 Test Metrics

### Coverage Targets

- **Unit Test Coverage:** 80%+
- **Integration Test Coverage:** 70%+
- **E2E Test Coverage:** Critical paths only

### Performance Targets

- **Estimated Time Accuracy:**
  - Chunking mode: ±15% margin
  - Non-chunking mode: ±20% margin

- **Status Update Frequency:**
  - Update every 1-2 seconds
  - Response time < 100ms

---

## ✅ Test Checklist

### Pre-Testing

- [ ] Test environment setup
- [ ] Test data preparation
- [ ] Test tools installation

### Unit Tests

- [ ] Status Messages Generation
- [ ] Estimated Time Calculation
- [ ] Progress Tracking Updates

### Integration Tests

- [ ] API Endpoints Response
- [ ] Worker Status Updates
- [ ] Progress Tracking Flow

### Manual Tests

- [ ] TC-1: Audio Extraction Status
- [ ] TC-2: Non-Chunking Transcription Status
- [ ] TC-3: Chunking Transcription Status
- [ ] TC-4: Non-Chunking Estimated Time
- [ ] TC-5: Chunking Estimated Time
- [ ] TC-6: Very Short Video
- [ ] TC-7: Very Long Video
- [ ] TC-8: First Chunk
- [ ] TC-9: Real-time Updates
- [ ] TC-10: Error Handling

### Performance Tests

- [ ] Estimated Time Accuracy (Chunking)
- [ ] Estimated Time Accuracy (Non-Chunking)
- [ ] Status Update Frequency
- [ ] Response Time

### E2E Tests

- [ ] Full Transcription Flow
- [ ] Status Updates During Processing
- [ ] Estimated Time Accuracy

---

## 📝 Test Report Template

```markdown
# Test Report: Status Messages & Estimated Time

## Test Summary
- Total Test Cases: XX
- Passed: XX
- Failed: XX
- Skipped: XX

## Test Results

### Unit Tests
- Status Messages: ✅ Pass
- Estimated Time: ✅ Pass

### Integration Tests
- API Endpoints: ✅ Pass
- Worker Updates: ✅ Pass

### Manual Tests
- TC-1: ✅ Pass
- TC-2: ✅ Pass
- ...

### Performance Tests
- Estimated Time Accuracy: ✅ Pass (±15% margin)
- Response Time: ✅ Pass (< 100ms)

## Issues Found
1. [Issue description]
2. [Issue description]

## Recommendations
1. [Recommendation]
2. [Recommendation]
```

---

**Last Updated**: 2024-12-05  
**Status**: Test Plan Complete ✅

