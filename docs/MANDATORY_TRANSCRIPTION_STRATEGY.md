# 📊 กลยุทธ์: Mandatory Transcription + Document Mapping Service

**วันที่สร้าง**: 2024-12-05  
**Purpose**: วิเคราะห์แนวทาง Mandatory Transcription + Background Mapping Service

---

## 📋 แนวทางที่เสนอ

### Core Concept

1. **ทุกวิดีโอต้อง Transcription**
   - ทุก Media file ที่อัปโหลด → Auto Transcription (optional)
   - User สามารถเลือกได้: `upload_only` หรือ `upload_transcription`
   - ได้ Text Reference สำหรับทุก Media file เสมอ

2. **Document Mapping Service**
   - Algorithm/Service สำหรับเทียบข้อความ Document → ChunkMapping (ID)
   - Trigger เมื่อ Save Document
   - แก้ปัญหา: Auto Save ทุก 30 วินาที → Process มากเกินไป

---

## ✅ ข้อดีของแนวทางนี้

### 1. มี Text Reference เสมอ
- ✅ ทุก Media file มี Transcription เป็น baseline
- ✅ สามารถใช้ Diff Algorithm ได้เสมอ (ไม่ต้อง Manual Tagging)
- ✅ Search accuracy สูง (มี reference point)

### 2. User Experience
- ✅ User ไม่ต้องกังวลว่าจะมี transcription หรือไม่
- ✅ สามารถเลือกได้ว่าจะ transcription ตอน upload หรือภายหลัง
- ✅ Auto-transcription ใน background

### 3. Mapping Accuracy
- ✅ Diff Algorithm ทำงานได้ดี (มี original text)
- ✅ ไม่ต้องพึ่ง Manual Tagging (ถ้าใช้ transcription)
- ✅ Support Manual Tagging สำหรับส่วนที่พิมพ์ใหม่

---

## ⚠️ ปัญหาและแนวทางแก้ไข

### ⚠️ **หมายเหตุ: ไม่สนใจ Auto Save**

**ตามความต้องการ:**
- **ไม่ต้อง process ทันที** เมื่อ Auto Save
- Process เฉพาะเมื่อ User **Save Manual** หรือ **Request Mapping** เท่านั้น
- ลดปัญหา Processing Overload โดยไม่ต้องใช้ optimization strategies

**Implementation:**
- Auto Save → **ไม่ trigger mapping**
- Manual Save → **Trigger mapping** (immediate หรือ background)
- Request Mapping API → **Trigger mapping** (background job)

---

### ~~ปัญหาหลัก: Auto Save → Processing Overload~~ (ไม่ใช้แล้ว)

~~**สถานการณ์:**~~
~~- Document Auto Save ทุก 30 วินาที~~
~~- ถ้า Save → Trigger Mapping Service ทุกครั้ง~~
~~- **10 documents × 1 save/30s = ~20 requests/minute**~~
~~- **อาจทำให้ service overload**~~

---

## 💡 วิธีแก้ปัญหา Auto Save

### **Solution 1: Debounced/Delayed Processing (แนะนำ)**

#### หลักการ
- **ไม่ process ทันที** เมื่อ auto save
- **รอให้ User หยุดแก้ไข** ก่อน process
- ใช้ **debounce/throttle** mechanism

#### Implementation

```typescript
interface DocumentMappingService {
  // Debounced mapping calculation
  private mappingQueue: Map<string, NodeJS.Timeout>;
  
  async requestMapping(documentId: string, debounceMs: number = 30000) {
    // Clear existing timeout
    if (this.mappingQueue.has(documentId)) {
      clearTimeout(this.mappingQueue.get(documentId)!);
    }
    
    // Set new timeout
    const timeout = setTimeout(async () => {
      await this.processMapping(documentId);
      this.mappingQueue.delete(documentId);
    }, debounceMs);
    
    this.mappingQueue.set(documentId, timeout);
  }
  
  // Manual save (immediate processing)
  async saveAndMap(documentId: string) {
    // Clear debounced request
    if (this.mappingQueue.has(documentId)) {
      clearTimeout(this.mappingQueue.get(documentId)!);
      this.mappingQueue.delete(documentId);
    }
    
    // Process immediately
    await this.processMapping(documentId);
  }
}
```

#### Flow

```
User แก้ไข Document
    ↓
Auto Save (ทุก 30s) → requestMapping(documentId, 30000ms)
    ↓
[Debounce: รอ 30 วินาที]
    ↓ (ถ้า User ยังแก้ไขต่อ → reset timer)
User หยุดแก้ไข → 30 วินาทีผ่านไป
    ↓
Process Mapping (background job)
    ↓
Update Document Mapping
```

#### ข้อดี
- ✅ **ลด Processing**: ไม่ process ทุก auto save
- ✅ **รอให้ User หยุดแก้ไข**: Process เมื่อเสร็จแล้ว
- ✅ **User-friendly**: Manual save → process ทันที

---

### **Solution 2: Background Job Queue**

#### หลักการ
- Auto Save → **Enqueue mapping job** (ไม่ process ทันที)
- Background worker **process jobs** ทีละตัว (rate limiting)
- **Deduplication**: ลบ duplicate jobs (same document)

#### Implementation

```typescript
interface MappingJobQueue {
  // Job queue with deduplication
  private queue: PriorityQueue<MappingJob>;
  private processing: Set<string>; // documentIds in progress
  
  async enqueueMappingJob(documentId: string, priority: 'low' | 'high' = 'low') {
    // Deduplication: Remove existing job for same document
    this.queue.remove(job => job.documentId === documentId);
    
    // Add new job
    this.queue.push({
      documentId,
      priority,
      enqueuedAt: Date.now()
    });
  }
  
  // Background worker
  async processJobs() {
    while (true) {
      const job = this.queue.pop();
      if (!job) {
        await sleep(1000);
        continue;
      }
      
      // Rate limiting: Process 1 job per 5 seconds
      if (this.processing.has(job.documentId)) {
        this.queue.push(job); // Requeue
        await sleep(5000);
        continue;
      }
      
      this.processing.add(job.documentId);
      try {
        await this.processMapping(job.documentId);
      } finally {
        this.processing.delete(job.documentId);
      }
    }
  }
}
```

#### ข้อดี
- ✅ **Rate Limiting**: ควบคุม processing rate
- ✅ **Deduplication**: ไม่ process ซ้ำ
- ✅ **Priority Queue**: Manual save → priority สูง
- ✅ **Scalable**: สามารถ scale workers ได้

---

### **Solution 3: Change Detection (แนะนำที่สุด)**

#### หลักการ
- **Track document changes**: เปรียบเทียบ content hash
- **Process เฉพาะเมื่อ content เปลี่ยนจริงๆ**
- Auto Save แต่ content เหมือนเดิม → ไม่ process

#### Implementation

```typescript
interface DocumentMappingService {
  // Cache: Last processed content hash
  private processedHashes: Map<string, string>;
  
  async requestMapping(documentId: string, documentContent: string) {
    // Calculate content hash
    const contentHash = hashString(documentContent);
    
    // Check if content changed
    const lastHash = this.processedHashes.get(documentId);
    if (lastHash === contentHash) {
      // Content ไม่เปลี่ยน → ไม่ต้อง process
      return { skipped: true, reason: 'no_changes' };
    }
    
    // Content เปลี่ยน → Process mapping
    const result = await this.processMapping(documentId, documentContent);
    
    // Update hash
    this.processedHashes.set(documentId, contentHash);
    
    return result;
  }
  
  private hashString(content: string): string {
    // Use SHA-256 or MD5 hash
    return crypto.createHash('sha256').update(content).digest('hex');
  }
}
```

#### Flow

```
Auto Save (ทุก 30s)
    ↓
Calculate Content Hash
    ↓
Compare with Last Hash
    ↓
[Hash เหมือนเดิม?]
    ├─ Yes → Skip Processing ✅
    └─ No → Process Mapping → Update Hash
```

#### ข้อดี
- ✅ **Efficient**: Process เฉพาะเมื่อ content เปลี่ยนจริงๆ
- ✅ **Simple**: Logic เรียบง่าย
- ✅ **No Queue Needed**: ไม่ต้อง queue management
- ✅ **Memory Efficient**: เก็บแค่ hash (ไม่เก็บ content)

---

### **Solution 4: Hybrid (Change Detection + Debounce)**

#### หลักการ
- **Combine**: Change Detection + Debounce
- **Best of both worlds**

#### Implementation

```typescript
interface DocumentMappingService {
  private processedHashes: Map<string, string>;
  private debounceTimers: Map<string, NodeJS.Timeout>;
  
  async requestMapping(
    documentId: string,
    documentContent: string,
    immediate: boolean = false
  ) {
    // Calculate hash
    const contentHash = hashString(documentContent);
    
    // Check if changed
    const lastHash = this.processedHashes.get(documentId);
    if (lastHash === contentHash && !immediate) {
      return { skipped: true, reason: 'no_changes' };
    }
    
    // Debounce (unless immediate)
    if (!immediate) {
      // Clear existing timer
      if (this.debounceTimers.has(documentId)) {
        clearTimeout(this.debounceTimers.get(documentId)!);
      }
      
      // Set new timer (30 seconds)
      const timeout = setTimeout(async () => {
        await this.processMapping(documentId, documentContent);
        this.processedHashes.set(documentId, contentHash);
        this.debounceTimers.delete(documentId);
      }, 30000);
      
      this.debounceTimers.set(documentId, timeout);
      return { queued: true, debounceMs: 30000 };
    }
    
    // Immediate (manual save)
    await this.processMapping(documentId, documentContent);
    this.processedHashes.set(documentId, contentHash);
    return { processed: true };
  }
}
```

#### ข้อดี
- ✅ **Change Detection**: ไม่ process ถ้าไม่เปลี่ยน
- ✅ **Debounce**: รอให้ User หยุดแก้ไข
- ✅ **Immediate for Manual Save**: Process ทันทีเมื่อ save manual

---

## 📊 เปรียบเทียบ Solutions

| Solution | Efficiency | Complexity | Latency | Best For |
|----------|-----------|-----------|---------|----------|
| **Debounce** | ⭐⭐⭐⭐ | ⭐⭐ | ⚠️ Delay | Simple cases |
| **Job Queue** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Low | High volume |
| **Change Detection** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ Immediate | Recommended |
| **Hybrid** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⚠️ Delay | Production |

---

## 🏗️ Architecture: Mandatory Transcription + Mapping Service

### 📍 **ตำแหน่งที่ต้อง Implement**

**✅ Senate-Backend (หลัก)**
- Document Mapping Service (C#)
- API Endpoints
- Database Tables
- Background Job (Hangfire)

**✅ Transcription Service (ไม่ต้องแก้ไข)**
- ใช้ API ที่มีอยู่แล้ว: `GET /transcription/{task_id}/chunks`

**❌ File Service (ไม่เกี่ยวข้อง)**
- ไม่เกี่ยวกับ Document Mapping Logic

**ดูรายละเอียดเพิ่มเติม:** [DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md](./DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md)

---

### Upload Flow

```typescript
// Upload with mode selection
interface UploadRequest {
  file: File;
  mode: 'upload_only' | 'upload_transcription';
  transcriptionOptions?: {
    language: string;
    modelSize: string;
    useChunking: boolean;
  };
}

async function uploadMedia(request: UploadRequest) {
  // 1. Upload file to FileService
  const fileId = await fileService.upload(request.file);
  
  // 2. Create Media record
  const media = await createMedia({
    fileId,
    fileName: request.file.name,
    status: 'uploaded'
  });
  
  // 3. Start transcription (if requested)
  if (request.mode === 'upload_transcription') {
    const transcriptionJob = await transcriptionService.startTranscription({
      fileId,
      ...request.transcriptionOptions
    });
    
    // Link transcription to media
    await linkTranscriptionToMedia(media.id, transcriptionJob.taskId);
  }
  
  return { mediaId: media.id, fileId };
}
```

### Document Mapping Service

**Implementation Location:** Senate-Backend (C#)

```csharp
public class DocumentMappingService : IDocumentMappingService
{
    public async Task<DocumentMappingResult> ProcessMappingAsync(
        Guid documentId,
        string documentContent,
        string transcriptionTaskId,
        CancellationToken cancellationToken = default)
    {
        // 1. Get transcription chunks from Transcription Service API
        var chunks = await GetTranscriptionChunksAsync(transcriptionTaskId, cancellationToken);
        
        // 2. Get original transcription text
        var originalText = string.Join(" ", chunks.Select(c => c.Text));
        
        // 3. Calculate word-level mapping
        var mappings = await MapDocumentToChunksAsync(
            documentContent,
            originalText,
            chunks,
            cancellationToken
        );
        
        // 4. Save mappings to database
        await SaveDocumentMappingsAsync(documentId, mappings, cancellationToken);
        
        return new DocumentMappingResult
        {
            DocumentId = documentId,
            TotalWords = mappings.Count,
            MappedWords = mappings.Count(m => m.MatchType != "interpolated"),
            Confidence = mappings.Average(m => m.Confidence)
        };
    }
    
    // Manual Save → Immediate processing (via Hangfire)
    // Request Mapping API → Background job
}
```

**Background Processing:**
- ใช้ **Hangfire** สำหรับ Background Job
- Manual Save → Enqueue Hangfire job (immediate)
- Request Mapping → Enqueue Hangfire job (background)

**ดูรายละเอียดเพิ่มเติม:** [DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md](./DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md)

---

## 📐 Data Model

### Media with Transcription

```typescript
interface Media {
  id: string;
  fileId: string;
  fileName: string;
  uploadMode: 'upload_only' | 'upload_transcription';
  transcriptionId?: string; // Reference to transcription (if exists)
  transcriptionStatus: 'pending' | 'processing' | 'completed' | 'failed' | 'none';
  createdAt: Date;
}

interface Document {
  id: string;
  content: string;
  mediaId?: string; // Reference to media (if from video)
  transcriptionId?: string; // Reference to transcription
  mappingVersion: number; // Increment when mapping changes
  lastMappedAt?: Date;
  lastMappingHash?: string; // Content hash when last mapped
}
```

### Database Schema

```sql
-- Media Table (extend existing)
ALTER TABLE media ADD COLUMN IF NOT EXISTS upload_mode VARCHAR(20) DEFAULT 'upload_only';
ALTER TABLE media ADD COLUMN IF NOT EXISTS transcription_id VARCHAR(100);
ALTER TABLE media ADD COLUMN IF NOT EXISTS transcription_status VARCHAR(20) DEFAULT 'none';

-- Document Mapping Table
CREATE TABLE document_mappings (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    transcription_id VARCHAR(100) NOT NULL,
    
    -- Mapping data (JSONB)
    word_mappings JSONB NOT NULL,
    
    -- Metadata
    mapping_version INTEGER NOT NULL DEFAULT 1,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256 hash
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    UNIQUE(document_id, mapping_version)
);

CREATE INDEX idx_document_mappings_document_id ON document_mappings(document_id);
CREATE INDEX idx_document_mappings_content_hash ON document_mappings(content_hash);
```

---

## 🔍 Mapping Algorithm (Simplified - No Order Change)

### Word-Level Mapping (Focus: Map to Chunks)

```typescript
interface WordMapping {
  documentWord: string;
  documentPosition: number;
  chunkId: string;
  chunkStartTime: number;
  chunkEndTime: number;
  matchType: 'exact' | 'fuzzy' | 'interpolated';
  confidence: number;
}

async function mapDocumentToChunks(
  documentContent: string,
  transcriptionChunks: TranscriptionChunk[]
): Promise<WordMapping[]> {
  // 1. Split document into words
  const documentWords = segmentWords(documentContent); // Thai word segmentation
  
  // 2. Build word index from transcription chunks
  const chunkWordIndex: Map<string, ChunkWordReference[]> = new Map();
  
  transcriptionChunks.forEach((chunk, chunkIndex) => {
    const chunkWords = segmentWords(chunk.text);
    chunkWords.forEach((word, wordIndex) => {
      if (!chunkWordIndex.has(word)) {
        chunkWordIndex.set(word, []);
      }
      chunkWordIndex.get(word)!.push({
        chunkId: chunk.chunkId || chunkIndex.toString(),
        chunkIndex,
        wordIndex,
        startTime: chunk.start_time,
        endTime: chunk.end_time,
        chunkText: chunk.text
      });
    });
  });
  
  // 3. Map document words to chunks
  const mappings: WordMapping[] = [];
  let documentPosition = 0;
  
  for (const word of documentWords) {
    // Try exact match first
    const chunkRefs = chunkWordIndex.get(word) || [];
    
    if (chunkRefs.length > 0) {
      // Use first occurrence (can be improved with context)
      const ref = chunkRefs[0];
      mappings.push({
        documentWord: word,
        documentPosition,
        chunkId: ref.chunkId,
        chunkStartTime: ref.startTime,
        chunkEndTime: ref.endTime,
        matchType: 'exact',
        confidence: 1.0
      });
    } else {
      // Fuzzy match or interpolate
      const fuzzyMatch = await findFuzzyMatch(word, chunkWordIndex);
      
      if (fuzzyMatch) {
        mappings.push({
          documentWord: word,
          documentPosition,
          chunkId: fuzzyMatch.chunkId,
          chunkStartTime: fuzzyMatch.startTime,
          chunkEndTime: fuzzyMatch.endTime,
          matchType: 'fuzzy',
          confidence: fuzzyMatch.confidence
        });
      } else {
        // Interpolate from neighboring words
        const interpolated = interpolateFromNeighbors(
          mappings,
          documentPosition
        );
        if (interpolated) {
          mappings.push({
            documentWord: word,
            documentPosition,
            chunkId: interpolated.chunkId,
            chunkStartTime: interpolated.startTime,
            chunkEndTime: interpolated.endTime,
            matchType: 'interpolated',
            confidence: 0.5
          });
        }
      }
    }
    
    documentPosition += word.length + 1; // +1 for space
  }
  
  return mappings;
}
```

---

## 🎯 Implementation Plan

### Phase 1: Mandatory Transcription Option

**Tasks:**
1. ✅ เพิ่ม `upload_mode` ใน Media upload API
2. ✅ Auto-start transcription เมื่อ `upload_transcription`
3. ✅ Track transcription status ใน Media
4. ✅ UI: Radio button เลือก mode (`upload_only` / `upload_transcription`)

**Duration:** 1 สัปดาห์

---

### Phase 2: Document Mapping Service

**Tasks:**
1. ✅ สร้าง `DocumentMappingService`
2. ✅ Implement Change Detection (hash-based)
3. ✅ Implement Debounce mechanism
4. ✅ Word-level mapping algorithm
5. ✅ Store mappings in database

**Duration:** 2-3 สัปดาห์

---

### Phase 3: Integration with Document Editor

**Tasks:**
1. ✅ Auto-save → Request mapping (debounced)
2. ✅ Manual save → Process immediately
3. ✅ Show mapping status in UI
4. ✅ Search integration with timestamps

**Duration:** 1-2 สัปดาห์

---

## 📊 Performance Analysis

### Auto Save Impact

**Scenario:**
- 10 documents กำลังแก้ไข
- Auto save ทุก 30 วินาที
- Mapping process time: ~2-5 วินาที/document

**Without Optimization:**
- Requests: 10 × 2/min = 20 requests/minute
- Processing: 20 × 3s = 60s/minute (100% CPU)
- **❌ Overload**

**With Change Detection:**
- Content เปลี่ยนจริง: ~10% ของ auto saves
- Requests: 10 × 0.1 × 2/min = 2 requests/minute
- Processing: 2 × 3s = 6s/minute (10% CPU)
- **✅ Efficient**

**With Change Detection + Debounce:**
- Same as above
- Plus: ไม่ process ระหว่างที่ User กำลังแก้ไข
- **✅ Very Efficient**

---

## ✅ สรุปและคำแนะนำ

### แนวทางที่แนะนำ: **Mandatory Transcription + Change Detection + Debounce**

**Implementation:**

1. **Upload Mode Selection**
   ```typescript
   uploadMode: 'upload_only' | 'upload_transcription'
   ```

2. **Auto Transcription** (ถ้าเลือก `upload_transcription`)
   - Background processing
   - Track status

3. **Document Mapping Service**
   - Change Detection (hash-based)
   - Debounce (30 seconds)
   - Manual Save → Immediate processing

4. **Mapping Algorithm**
   - Word-level mapping
   - Focus on chunk mapping (ไม่สนใจ order change)
   - Interpolation สำหรับ unmatched words

---

## 📝 API Design

### Upload API

```typescript
POST /api/media/upload
{
  "file": File,
  "mode": "upload_transcription", // or "upload_only"
  "transcriptionOptions": {
    "language": "th",
    "modelSize": "base",
    "useChunking": true
  }
}

Response:
{
  "mediaId": "uuid",
  "fileId": "uuid",
  "transcriptionJobId": "task-id" // if mode = upload_transcription
}
```

### Document Mapping API

**Implementation Location:** Senate-Backend (C# Controller)

```csharp
// Request mapping (Manual Save หรือ Request Mapping API)
POST /api/documents/{documentId}/mapping/request
{
  "content": "document content",
  "transcriptionJobId": 123
}

Response:
{
  "jobId": "hangfire-job-123",
  "status": "queued",
  "documentId": "uuid",
  "estimatedTime": 5000
}

// Get mapping status
GET /api/documents/{documentId}/mapping/status

Response:
{
  "documentId": "uuid",
  "mappingVersion": 1,
  "status": "completed",
  "totalWords": 1500,
  "mappedWords": 1450,
  "confidence": 0.95,
  "lastMappedAt": "2024-12-05T10:00:00Z"
}

// Get mapping results (for Search)
GET /api/documents/{documentId}/mapping/results

Response:
{
  "documentId": "uuid",
  "mappings": [
    {
      "documentWord": "คำ",
      "documentPosition": 0,
      "chunkIndex": 0,
      "chunkStartTime": 0.0,
      "chunkEndTime": 5.2,
      "matchType": "exact",
      "confidence": 1.0
    }
  ]
}
```

**หมายเหตุ:**
- **Auto Save ไม่ trigger mapping** (ตามความต้องการ)
- **Manual Save → Trigger mapping** (via Hangfire)
- **Request Mapping API → Trigger mapping** (via Hangfire)

**ดูรายละเอียดเพิ่มเติม:** [DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md](./DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md)

---

**Last Updated**: 2024-12-05  
**Status**: Analysis Complete ✅

