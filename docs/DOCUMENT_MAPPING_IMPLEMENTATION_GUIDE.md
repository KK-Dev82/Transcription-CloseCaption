# 📊 คู่มือการ Implement: Document Mapping Service

**วันที่สร้าง**: 2024-12-05  
**Purpose**: คู่มือการ implement Document Mapping Service สำหรับ Map ข้อความจาก Document กับ Transcription Text เพื่อแสดง Video/Audio Timing ที่ถูกต้อง

---

## 📋 สรุปแนวทาง

### Core Concept

1. **Document Mapping Service**
   - Map ข้อความจาก Document (ที่ User แก้ไข) กับ Transcription Text (ต้นฉบับ)
   - ใช้ Chunk Metadata (start_time, end_time) เป็นตัวช่วย
   - ส่งผลให้ Search สามารถแสดง Video Timestamp ได้ถูกต้อง

2. **ไม่สนใจ Auto Save**
   - **ไม่ต้อง process ทันที** เมื่อ Auto Save
   - Process เมื่อ User **Save Manual** หรือ **Request Mapping** เท่านั้น
   - ลดปัญหา Processing Overload

---

## 🏗️ Architecture: ต้อง Implement ที่ไหน?

### ✅ **Senate-Backend** (หลัก - ต้อง Implement)

**เหตุผล:**
- Document Mapping เป็น **Business Logic** ที่เกี่ยวกับ Document Management
- ต้องเข้าถึง Database (documents, transcription_jobs)
- ต้องเรียก Transcription Service API เพื่อดึง chunks
- ต้องเก็บ mapping results ใน Database

**สิ่งที่ต้อง Implement:**

1. **DocumentMappingService** (C# Service)
   - Word-level mapping algorithm
   - Diff calculation (Document vs Transcription)
   - Chunk mapping logic

2. **DocumentMappingController** (API Endpoints)
   - `POST /api/documents/{documentId}/mapping/request` - Request mapping
   - `GET /api/documents/{documentId}/mapping/status` - Get mapping status
   - `GET /api/documents/{documentId}/mapping/results` - Get mapping results

3. **Database Tables**
   - `document_mappings` - เก็บ mapping results
   - `document_time_tags` - เก็บ manual time tags (ถ้ามี)

4. **Background Job** (Hangfire หรือ RabbitMQ)
   - Process mapping ใน background
   - ไม่ block API response

---

### ✅ **Transcription Service** (ไม่ต้องแก้ไข - แค่ใช้ API)

**เหตุผล:**
- Transcription Service **มี API อยู่แล้ว** สำหรับดึง chunks
- ไม่ต้องแก้ไข Transcription Service

**API ที่ใช้:**

```http
GET /transcription/{task_id}/chunks
```

**Response:**
```json
{
  "task_id": "task-123",
  "chunks": [
    {
      "start_time": 0.0,
      "end_time": 5.2,
      "text": "คำพูดของผู้ประชุม...",
      "confidence": 0.95
    },
    {
      "start_time": 5.2,
      "end_time": 10.5,
      "text": "ข้อความต่อไป...",
      "confidence": 0.92
    }
  ],
  "total_chunks": 120
}
```

**Implementation:**
- Senate-Backend เรียก API นี้เพื่อดึง chunks
- ใช้ chunks สำหรับ mapping algorithm

---

### ❌ **File Service** (ไม่เกี่ยวข้อง)

**เหตุผล:**
- File Service เป็นแค่ file storage
- ไม่เกี่ยวกับ Document Mapping Logic

---

## 🔄 ต้องใช้ Hangfire หรือ RabbitMQ ไหม?

### ✅ **แนะนำ: ใช้ Hangfire** (สำหรับ Background Processing)

**เหตุผล:**
- Senate-Backend **มี Hangfire อยู่แล้ว**
- เหมาะกับ Background Jobs ที่ใช้เวลานาน (2-5 วินาที)
- ง่ายต่อการจัดการ (retry, monitoring)

**Implementation:**

```csharp
// ใน DocumentMappingController
[HttpPost("documents/{documentId}/mapping/request")]
public async Task<IActionResult> RequestMapping(
    Guid documentId,
    [FromBody] MappingRequest request,
    CancellationToken cancellationToken = default)
{
    // 1. Validate document exists
    var document = await _unitOfWork.SnChapterDocument
        .FirstOrDefaultAsync(d => d.Id == documentId, cancellationToken);
    
    if (document == null)
        return NotFound();
    
    // 2. Check if transcription exists
    var transcriptionJob = await _unitOfWork.TranscriptionJobs
        .FirstOrDefaultAsync(j => j.Id == request.TranscriptionJobId, cancellationToken);
    
    if (transcriptionJob == null || transcriptionJob.Result == null)
        return BadRequest("Transcription not found or not completed");
    
    // 3. Enqueue Hangfire job
    var jobId = BackgroundJob.Enqueue<IDocumentMappingService>(
        service => service.ProcessMappingAsync(documentId, request.Content, transcriptionJob.TaskId, cancellationToken)
    );
    
    return Accepted(new
    {
        jobId = jobId,
        status = "queued",
        documentId = documentId
    });
}
```

**Hangfire Service:**

```csharp
public interface IDocumentMappingService
{
    Task<DocumentMappingResult> ProcessMappingAsync(
        Guid documentId,
        string documentContent,
        string transcriptionTaskId,
        CancellationToken cancellationToken = default);
}

public class DocumentMappingService : IDocumentMappingService
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<DocumentMappingService> _logger;
    
    public async Task<DocumentMappingResult> ProcessMappingAsync(
        Guid documentId,
        string documentContent,
        string transcriptionTaskId,
        CancellationToken cancellationToken = default)
    {
        // 1. Get transcription chunks from Transcription Service
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
    
    private async Task<List<TranscriptionChunk>> GetTranscriptionChunksAsync(
        string taskId,
        CancellationToken cancellationToken)
    {
        var transcriptionUrl = _configuration["ExternalServices:TranscriptionUrl"]?.TrimEnd('/');
        var client = _httpClientFactory.CreateClient();
        
        var response = await client.GetAsync(
            $"{transcriptionUrl}/transcription/{taskId}/chunks",
            cancellationToken
        );
        
        response.EnsureSuccessStatusCode();
        
        var result = await response.Content.ReadFromJsonAsync<TranscriptionChunksResponse>(
            cancellationToken: cancellationToken
        );
        
        return result?.Chunks ?? new List<TranscriptionChunk>();
    }
    
    private async Task<List<WordMapping>> MapDocumentToChunksAsync(
        string documentContent,
        string originalText,
        List<TranscriptionChunk> chunks,
        CancellationToken cancellationToken)
    {
        // Word-level mapping algorithm (ดูรายละเอียดด้านล่าง)
        // ...
    }
}
```

---

### ⚠️ **Alternative: ใช้ RabbitMQ** (ถ้าต้องการ Async Processing แบบ Distributed)

**เหตุผล:**
- ถ้าต้องการ scale workers แยกต่างหาก
- ถ้าต้องการ distributed processing

**Implementation:**

```csharp
// Publish mapping request to RabbitMQ
await _rabbitMqService.PublishAsync("document.mapping.request", new
{
    documentId = documentId,
    content = request.Content,
    transcriptionTaskId = transcriptionJob.TaskId
});

// Consumer (ใน Background Service)
public class DocumentMappingConsumer : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        // Consume from "document.mapping.request" queue
        // Process mapping
        // Publish result to "document.mapping.completed"
    }
}
```

**ข้อดี:**
- ✅ Distributed processing
- ✅ Scale workers ได้

**ข้อเสีย:**
- ⚠️ Complexity สูงกว่า Hangfire
- ⚠️ ต้องจัดการ queue, consumer

---

## 📐 Data Model

### Database Schema (PostgreSQL)

```sql
-- Document Mappings Table
CREATE TABLE document_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    transcription_task_id VARCHAR(100) NOT NULL,
    
    -- Mapping data (JSONB)
    word_mappings JSONB NOT NULL,
    
    -- Metadata
    mapping_version INTEGER NOT NULL DEFAULT 1,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256 hash
    total_words INTEGER NOT NULL,
    mapped_words INTEGER NOT NULL,
    confidence DECIMAL(3,2), -- 0.00-1.00
    
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT fk_document_mappings_document 
        FOREIGN KEY (document_id) 
        REFERENCES sn_chapter_documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_document_mappings_document_id 
    ON document_mappings(document_id);
CREATE INDEX idx_document_mappings_transcription_task_id 
    ON document_mappings(transcription_task_id);
CREATE INDEX idx_document_mappings_content_hash 
    ON document_mappings(content_hash);

-- Word Mappings JSONB Structure:
-- [
--   {
--     "documentWord": "คำ",
--     "documentPosition": 0,
--     "chunkIndex": 0,
--     "chunkStartTime": 0.0,
--     "chunkEndTime": 5.2,
--     "matchType": "exact" | "fuzzy" | "interpolated",
--     "confidence": 0.95
--   },
--   ...
-- ]
```

### C# Models

```csharp
public class DocumentMapping
{
    public Guid Id { get; set; }
    public Guid DocumentId { get; set; }
    public string TranscriptionTaskId { get; set; }
    public List<WordMapping> WordMappings { get; set; }
    public int MappingVersion { get; set; }
    public string ContentHash { get; set; }
    public int TotalWords { get; set; }
    public int MappedWords { get; set; }
    public decimal? Confidence { get; set; }
    public DateTime ProcessedAt { get; set; }
    public DateTime CreatedAt { get; set; }
}

public class WordMapping
{
    public string DocumentWord { get; set; }
    public int DocumentPosition { get; set; }
    public int ChunkIndex { get; set; }
    public decimal ChunkStartTime { get; set; }
    public decimal ChunkEndTime { get; set; }
    public string MatchType { get; set; } // "exact", "fuzzy", "interpolated"
    public decimal Confidence { get; set; }
}

public class TranscriptionChunk
{
    public decimal StartTime { get; set; }
    public decimal EndTime { get; set; }
    public string Text { get; set; }
    public decimal? Confidence { get; set; }
}
```

---

## 🔍 Mapping Algorithm (Word-Level)

### หลักการ

1. **Split Document และ Transcription เป็น Words**
   - ใช้ Thai Word Segmentation (ถ้ามี library)
   - หรือ Split ด้วย space (สำหรับภาษาอังกฤษ)

2. **Build Word Index จาก Transcription Chunks**
   - สร้าง Map<word, List<ChunkReference>>
   - แต่ละ word มี reference ไปยัง chunk ที่มี word นั้น

3. **Map Document Words ไปยัง Chunks**
   - Exact match: หา word ใน index
   - Fuzzy match: ใช้ Levenshtein distance (ถ้าไม่เจอ exact)
   - Interpolate: ใช้ neighboring words (ถ้าไม่เจอเลย)

### Implementation (C#)

```csharp
public class DocumentMappingService : IDocumentMappingService
{
    public async Task<List<WordMapping>> MapDocumentToChunksAsync(
        string documentContent,
        string originalText,
        List<TranscriptionChunk> chunks,
        CancellationToken cancellationToken = default)
    {
        // 1. Split document into words
        var documentWords = SegmentWords(documentContent);
        
        // 2. Build word index from transcription chunks
        var chunkWordIndex = BuildChunkWordIndex(chunks);
        
        // 3. Map document words to chunks
        var mappings = new List<WordMapping>();
        int documentPosition = 0;
        
        foreach (var word in documentWords)
        {
            // Try exact match first
            var chunkRefs = chunkWordIndex.GetValueOrDefault(word, new List<ChunkWordReference>());
            
            if (chunkRefs.Count > 0)
            {
                // Use first occurrence (can be improved with context)
                var ref = chunkRefs[0];
                mappings.Add(new WordMapping
                {
                    DocumentWord = word,
                    DocumentPosition = documentPosition,
                    ChunkIndex = ref.ChunkIndex,
                    ChunkStartTime = ref.StartTime,
                    ChunkEndTime = ref.EndTime,
                    MatchType = "exact",
                    Confidence = 1.0m
                });
            }
            else
            {
                // Fuzzy match or interpolate
                var fuzzyMatch = FindFuzzyMatch(word, chunkWordIndex);
                
                if (fuzzyMatch != null)
                {
                    mappings.Add(new WordMapping
                    {
                        DocumentWord = word,
                        DocumentPosition = documentPosition,
                        ChunkIndex = fuzzyMatch.ChunkIndex,
                        ChunkStartTime = fuzzyMatch.StartTime,
                        ChunkEndTime = fuzzyMatch.EndTime,
                        MatchType = "fuzzy",
                        Confidence = fuzzyMatch.Confidence
                    });
                }
                else
                {
                    // Interpolate from neighboring words
                    var interpolated = InterpolateFromNeighbors(mappings, documentPosition, chunks);
                    if (interpolated != null)
                    {
                        mappings.Add(interpolated);
                    }
                }
            }
            
            documentPosition += word.Length + 1; // +1 for space
        }
        
        return mappings;
    }
    
    private List<string> SegmentWords(string text)
    {
        // TODO: Implement Thai word segmentation
        // For now, split by space (simple approach)
        return text.Split(new[] { ' ', '\n', '\r', '\t' }, 
            StringSplitOptions.RemoveEmptyEntries).ToList();
    }
    
    private Dictionary<string, List<ChunkWordReference>> BuildChunkWordIndex(
        List<TranscriptionChunk> chunks)
    {
        var index = new Dictionary<string, List<ChunkWordReference>>();
        
        for (int chunkIndex = 0; chunkIndex < chunks.Count; chunkIndex++)
        {
            var chunk = chunks[chunkIndex];
            var words = SegmentWords(chunk.Text);
            
            for (int wordIndex = 0; wordIndex < words.Count; wordIndex++)
            {
                var word = words[wordIndex];
                
                if (!index.ContainsKey(word))
                {
                    index[word] = new List<ChunkWordReference>();
                }
                
                index[word].Add(new ChunkWordReference
                {
                    ChunkIndex = chunkIndex,
                    WordIndex = wordIndex,
                    StartTime = chunk.StartTime,
                    EndTime = chunk.EndTime,
                    ChunkText = chunk.Text
                });
            }
        }
        
        return index;
    }
    
    private ChunkWordReference? FindFuzzyMatch(
        string word,
        Dictionary<string, List<ChunkWordReference>> chunkWordIndex,
        decimal threshold = 0.8m)
    {
        // Simple Levenshtein distance (can be improved)
        foreach (var kvp in chunkWordIndex)
        {
            var similarity = CalculateSimilarity(word, kvp.Key);
            if (similarity >= threshold)
            {
                return kvp.Value[0]; // Use first occurrence
            }
        }
        
        return null;
    }
    
    private decimal CalculateSimilarity(string s1, string s2)
    {
        // Simple Levenshtein distance-based similarity
        int maxLen = Math.Max(s1.Length, s2.Length);
        if (maxLen == 0) return 1.0m;
        
        int distance = LevenshteinDistance(s1, s2);
        return 1.0m - (decimal)distance / maxLen;
    }
    
    private int LevenshteinDistance(string s1, string s2)
    {
        // TODO: Implement Levenshtein distance algorithm
        // For now, return simple comparison
        return s1 == s2 ? 0 : Math.Abs(s1.Length - s2.Length);
    }
    
    private WordMapping? InterpolateFromNeighbors(
        List<WordMapping> existingMappings,
        int documentPosition,
        List<TranscriptionChunk> chunks)
    {
        // Find nearest mapped words before and after
        var before = existingMappings.LastOrDefault(m => m.DocumentPosition < documentPosition);
        var after = existingMappings.FirstOrDefault(m => m.DocumentPosition > documentPosition);
        
        if (before == null && after == null)
        {
            // No neighbors, use first chunk
            if (chunks.Count > 0)
            {
                return new WordMapping
                {
                    DocumentPosition = documentPosition,
                    ChunkIndex = 0,
                    ChunkStartTime = chunks[0].StartTime,
                    ChunkEndTime = chunks[0].EndTime,
                    MatchType = "interpolated",
                    Confidence = 0.5m
                };
            }
            return null;
        }
        
        // Interpolate between before and after
        if (before != null && after != null)
        {
            // Use average of before and after
            var avgStartTime = (before.ChunkStartTime + after.ChunkStartTime) / 2;
            var avgEndTime = (before.ChunkEndTime + after.ChunkEndTime) / 2;
            var avgChunkIndex = (before.ChunkIndex + after.ChunkIndex) / 2;
            
            return new WordMapping
            {
                DocumentPosition = documentPosition,
                ChunkIndex = avgChunkIndex,
                ChunkStartTime = avgStartTime,
                ChunkEndTime = avgEndTime,
                MatchType = "interpolated",
                Confidence = 0.5m
            };
        }
        
        // Use before or after
        var reference = before ?? after;
        return new WordMapping
        {
            DocumentPosition = documentPosition,
            ChunkIndex = reference.ChunkIndex,
            ChunkStartTime = reference.ChunkStartTime,
            ChunkEndTime = reference.ChunkEndTime,
            MatchType = "interpolated",
            Confidence = 0.5m
        };
    }
}

public class ChunkWordReference
{
    public int ChunkIndex { get; set; }
    public int WordIndex { get; set; }
    public decimal StartTime { get; set; }
    public decimal EndTime { get; set; }
    public string ChunkText { get; set; }
}
```

---

## 📝 API Design

### Request Mapping

```http
POST /api/documents/{documentId}/mapping/request
Content-Type: application/json

{
  "content": "document content here...",
  "transcriptionJobId": 123,
  "immediate": false
}
```

**Response:**
```json
{
  "jobId": "hangfire-job-123",
  "status": "queued",
  "documentId": "uuid",
  "estimatedTime": 5000
}
```

### Get Mapping Status

```http
GET /api/documents/{documentId}/mapping/status
```

**Response:**
```json
{
  "documentId": "uuid",
  "mappingVersion": 1,
  "status": "completed",
  "totalWords": 1500,
  "mappedWords": 1450,
  "confidence": 0.95,
  "lastMappedAt": "2024-12-05T10:00:00Z"
}
```

### Get Mapping Results

```http
GET /api/documents/{documentId}/mapping/results
```

**Response:**
```json
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
    },
    ...
  ],
  "totalWords": 1500,
  "mappedWords": 1450
}
```

### Search with Timestamps

```http
GET /api/documents/{documentId}/search?query=คำค้นหา
```

**Response:**
```json
{
  "query": "คำค้นหา",
  "results": [
    {
      "text": "คำค้นหาที่เจอ",
      "startTime": 123.5,
      "endTime": 128.7,
      "confidence": 1.0,
      "source": "exact"
    },
    ...
  ]
}
```

---

## 🎯 Implementation Plan

### Phase 1: Core Mapping Service (2-3 สัปดาห์)

**Tasks:**
1. ✅ สร้าง `DocumentMappingService` (C#)
2. ✅ Implement Word-level mapping algorithm
3. ✅ สร้าง Database tables (`document_mappings`)
4. ✅ สร้าง API Endpoints (`DocumentMappingController`)
5. ✅ Integrate with Hangfire (Background Job)

**Files to Create:**
- `src/Shorthand.Api/Services/DocumentMappingService.cs`
- `src/Shorthand.Api/Controllers/DocumentMappingController.cs`
- `src/Shorthand.Api/Models/DocumentMapping.cs`
- `migrations/AddDocumentMappingsTable.cs`

---

### Phase 2: Integration with Transcription Service (1 สัปดาห์)

**Tasks:**
1. ✅ เรียก Transcription Service API (`/transcription/{task_id}/chunks`)
2. ✅ Parse chunks response
3. ✅ Handle errors (transcription not found, not completed)

---

### Phase 3: Search Integration (1 สัปดาห์)

**Tasks:**
1. ✅ Integrate mapping results กับ Search API
2. ✅ Return timestamps ใน search results
3. ✅ Display timestamps ใน Frontend

---

## 📊 Performance Considerations

### Mapping Processing Time

**Estimated:**
- Document 1,500 words: ~2-5 วินาที
- Document 5,000 words: ~5-10 วินาที

**Optimization:**
- Cache transcription chunks (ไม่ต้องเรียก API ทุกครั้ง)
- Use Hangfire background processing (ไม่ block API)
- Batch processing สำหรับหลาย documents

---

## ✅ สรุป

### สิ่งที่ต้อง Implement

1. **Senate-Backend**
   - ✅ `DocumentMappingService` (C#)
   - ✅ `DocumentMappingController` (API)
   - ✅ Database tables (`document_mappings`)
   - ✅ Hangfire Background Job

2. **Transcription Service**
   - ❌ **ไม่ต้องแก้ไข** - แค่ใช้ API ที่มีอยู่แล้ว

3. **File Service**
   - ❌ **ไม่เกี่ยวข้อง**

### ใช้ Hangfire หรือ RabbitMQ?

**แนะนำ: ใช้ Hangfire**
- ✅ มีอยู่แล้วใน Senate-Backend
- ✅ เหมาะกับ Background Jobs
- ✅ ง่ายต่อการจัดการ

**Alternative: RabbitMQ**
- ⚠️ ใช้ถ้าต้องการ distributed processing
- ⚠️ Complexity สูงกว่า

---

**Last Updated**: 2024-12-05  
**Status**: Implementation Guide Complete ✅

