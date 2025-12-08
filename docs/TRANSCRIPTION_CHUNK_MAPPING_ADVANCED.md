# 📊 การวิเคราะห์ขั้นสูง: Map ข้อความที่พิมพ์ใหม่/Speech To Text กลับไปยัง Video Timestamps

**วันที่สร้าง**: 2024-12-05  
**Purpose**: วิเคราะห์กรณีพิเศษที่ User พิมพ์ใหม่ทั้งหมดหรือใช้ Speech To Text

**📌 หมายเหตุ:** สำหรับ Implementation Guide ที่ครอบคลุมทุกกรณี รวมถึงตำแหน่งที่ต้อง implement และการใช้ Hangfire/RabbitMQ ดูที่: [DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md](./DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md)

---

## 📋 กรณีพิเศษ (Special Cases)

### ปัญหา

1. **User พิมพ์ใหม่ทั้งหมด** (ไม่ใช้ Transcription)
   - ข้อความที่พิมพ์ ≠ ข้อความจาก Transcription
   - ไม่สามารถใช้ diff algorithm ได้ (ไม่มี common text)
   - ต้องหาวิธี map กลับไปยัง chunks/timestamps

2. **User ใช้ Speech To Text (Web Speech API)**
   - อาจมี timestamp จาก Speech API (ถ้า Web Speech API รองรับ)
   - แต่ความแม่นยำอาจไม่เท่า Transcription Service
   - ต้อง align กับ video timestamps

3. **ข้อจำกัด: ไม่สนใจ Order Change**
   - ต้องการแค่ Map word/phrase ให้ตรงตามช่วงเวลาของ chunk
   - ไม่ต้อง track การย้ายลำดับ

---

## 💡 แนวทางสำหรับกรณีพิเศษ

### **Approach 1: Manual Time Tagging (แนะนำสำหรับพิมพ์ใหม่)**

#### หลักการ

- User **tag ช่วงเวลา** ระหว่างการพิมพ์/แก้ไข
- เก็บ time tags ใน document metadata
- ใช้ time tags สำหรับ search mapping

#### Implementation

```typescript
interface TimeTag {
  documentPosition: number; // Character position in document
  startTime: number; // Video timestamp (seconds)
  endTime: number; // Video timestamp (seconds)
  confidence: 'manual' | 'auto' | 'estimated';
}

interface DocumentWithTimeTags {
  documentId: string;
  content: string;
  timeTags: TimeTag[]; // Sorted by documentPosition
  transcriptionId?: string; // Optional: reference to original transcription
}
```

#### User Experience

**Option A: Manual Tagging UI**
```
[Document Editor]
Text: "คำพูดของผู้ประชุม..."
      [Tag Time: 00:05:23]
      
[Time Tagging Panel]
- Click to add time tag
- Drag to adjust time range
- Link text selection to video timestamp
```

**Option B: Semi-Automatic (Play & Type)**
```
[Video Player] + [Document Editor]
- User play video
- Type text as they watch
- Auto-tag with current video timestamp
```

#### ข้อดี
- ✅ **แม่นยำ 100%**: User กำหนด timestamp เอง
- ✅ **รองรับทุกกรณี**: ไม่ว่า text จะมาจากไหน
- ✅ **เรียบง่าย**: ไม่ต้องใช้ complex algorithm

#### ข้อเสีย
- ⚠️ **Manual work**: User ต้อง tag เอง (อาจใช้เวลานาน)
- ⚠️ **User experience**: ต้องเพิ่ม UI สำหรับ tagging

---

### **Approach 2: Speech To Text with Timestamps**

#### หลักการ

- ใช้ Web Speech API (ถ้ารองรับ timestamps)
- หรือใช้ Speech Recognition API ที่ให้ timestamps
- Align timestamps จาก Speech API กับ Video

#### Implementation

```typescript
interface SpeechRecognitionResult {
  text: string;
  startTime: number; // Timestamp from Speech API (relative to recording start)
  endTime: number;
  confidence: number;
}

interface DocumentFromSpeech {
  documentId: string;
  content: string;
  speechSegments: SpeechRecognitionResult[];
  videoOffset: number; // Offset to align with video (if different)
}
```

#### Web Speech API Limitations

**⚠️ ข้อจำกัด:**
- Web Speech API **ไม่ให้ timestamps** โดยตรง
- ต้องใช้ alternative APIs:
  - Azure Speech Services
  - Google Cloud Speech-to-Text
  - AWS Transcribe

#### Alternative: Hybrid Approach

```typescript
// 1. Use Transcription Service as baseline
const transcriptionChunks = await getTranscriptionChunks(videoId);

// 2. User corrects/rewrites using Speech To Text
const speechText = await speechToText(audioSegment);

// 3. Map speech segments to video timestamps using audio alignment
const alignedSegments = await alignAudioTimestamps(
  speechText,
  audioSegment,
  transcriptionChunks // Use as reference
);
```

#### ข้อดี
- ✅ **Automatic**: ไม่ต้อง tag manual
- ✅ **แม่นยำ**: ถ้า Speech API ให้ timestamps

#### ข้อเสีย
- ⚠️ **API Dependency**: ต้องใช้ Speech API ที่ให้ timestamps
- ⚠️ **Cost**: อาจมีค่าใช้จ่าย
- ⚠️ **Web Speech API**: ไม่รองรับ timestamps

---

### **Approach 3: Fuzzy Matching with Time Hints**

#### หลักการ

- ใช้ Transcription chunks เป็น "hint" สำหรับ timestamp
- Fuzzy match ระหว่าง text ที่พิมพ์กับ transcription chunks
- ใช้ semantic similarity สำหรับส่วนที่ไม่ตรงกัน

#### Implementation

```typescript
interface FuzzyMapping {
  documentText: string;
  documentPosition: number;
  matchedChunkId?: string;
  matchedTimestamp?: number;
  confidence: number; // 0-1 (ความมั่นใจในการ match)
  matchType: 'exact' | 'fuzzy' | 'semantic' | 'estimated';
}

async function fuzzyMapToTimestamps(
  documentText: string,
  transcriptionChunks: TranscriptionChunk[]
): Promise<FuzzyMapping[]> {
  // 1. Try exact word matching
  const exactMatches = findExactMatches(documentText, transcriptionChunks);
  
  // 2. Try fuzzy matching (Levenshtein distance)
  const fuzzyMatches = findFuzzyMatches(documentText, transcriptionChunks, {
    threshold: 0.8 // 80% similarity
  });
  
  // 3. Try semantic similarity (NLP)
  const semanticMatches = await findSemanticMatches(
    documentText,
    transcriptionChunks
  );
  
  // 4. Interpolate timestamps for unmatched sections
  const interpolated = interpolateTimestamps(
    documentText,
    exactMatches,
    fuzzyMatches,
    semanticMatches
  );
  
  return interpolated;
}
```

#### ข้อดี
- ✅ **Semi-automatic**: ไม่ต้อง tag manual ทั้งหมด
- ✅ **รองรับทุกกรณี**: ทำงานได้แม้ text ต่างกันมาก

#### ข้อเสีย
- ❌ **ไม่แม่นยำ**: อาจมี error โดยเฉพาะส่วนที่ต่างกันมาก
- ❌ **Complexity**: Algorithm ซับซ้อน

---

### **Approach 4: Hybrid: Transcription Reference + Manual Override**

#### หลักการ (แนะนำสำหรับ Production)

**ขั้นตอน:**

1. **Load Transcription เป็น Baseline**
   - แสดง Transcription text ใน editor
   - User สามารถแก้ไข/พิมพ์ทับ/ลบได้

2. **Auto-map ตาม Diff Algorithm**
   - สำหรับส่วนที่ User แก้ไข (diff from original)
   - Map กลับไปยัง original chunks

3. **Manual Tagging สำหรับส่วนใหม่**
   - สำหรับส่วนที่ User เพิ่มใหม่ (ไม่มีใน transcription)
   - User tag timestamp manually หรือ play & type

4. **Speech To Text Integration**
   - ถ้าใช้ Speech To Text → auto-tag ด้วย timestamp จาก Speech API
   - Fallback: manual tagging

#### Implementation

```typescript
interface DocumentMapping {
  documentId: string;
  transcriptionId?: string; // Reference to original transcription
  content: string;
  
  // Hybrid mapping
  mappings: TextMapping[];
}

interface TextMapping {
  documentRange: { start: number; end: number };
  videoTimestamp?: number; // From transcription chunk
  timeTag?: TimeTag; // Manual tag
  speechTimestamp?: number; // From Speech To Text
  source: 'transcription' | 'manual' | 'speech' | 'estimated';
  confidence: number;
}

// Algorithm:
// 1. If has transcriptionId: Use diff algorithm
// 2. If manual tags exist: Use manual tags
// 3. If speech timestamps exist: Use speech timestamps
// 4. Interpolate for unmapped sections
```

#### ข้อดี
- ✅ **ยืดหยุ่น**: รองรับทุกกรณี
- ✅ **แม่นยำ**: Manual tagging สำหรับส่วนสำคัญ
- ✅ **User-friendly**: Auto-map ส่วนที่แก้ไขน้อย

#### ข้อเสีย
- ⚠️ **UI Complexity**: ต้องมี UI สำหรับหลายกรณี

---

## 📊 เปรียบเทียบแนวทาง

| Approach | Accuracy | UX | Complexity | Use Case |
|----------|----------|-----|------------|----------|
| **Manual Tagging** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | พิมพ์ใหม่ทั้งหมด |
| **Speech To Text** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Speech To Text |
| **Fuzzy Matching** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Mixed editing |
| **Hybrid** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ทุกกรณี (แนะนำ) |

---

## ✅ คำแนะนำสำหรับกรณีของคุณ

### Scenario 1: User พิมพ์ใหม่ทั้งหมด

**แนะนำ: Manual Time Tagging (Approach 1)**

**Implementation:**
```typescript
// 1. Document Editor with Time Tagging UI
interface DocumentEditor {
  content: string;
  timeTags: TimeTag[];
  
  // User actions:
  - Click to add time tag at cursor
  - Link text selection to video timestamp
  - Play video while typing (auto-tag)
}

// 2. Search with Time Tags
function searchWithTimestamps(query: string): SearchResult[] {
  // Find matches in document
  const matches = findTextMatches(document.content, query);
  
  // Map to timestamps using time tags
  const results = matches.map(match => {
    const timeTag = findTimeTagForPosition(
      document.timeTags,
      match.position
    );
    
    return {
      text: match.text,
      timestamp: timeTag?.startTime,
      confidence: 'manual'
    };
  });
  
  return results;
}
```

---

### Scenario 2: User ใช้ Speech To Text

**แนะนำ: Hybrid (Approach 4) + Speech API Timestamps**

**Implementation:**

**Option A: Speech API with Timestamps**
```typescript
// Use Speech API that provides timestamps
const speechResult = await azureSpeechService.recognize(audioFile, {
  format: 'detailed', // Include timestamps
  language: 'th-TH'
});

// speechResult.segments has timestamps
interface SpeechSegment {
  text: string;
  offset: number; // milliseconds from start
  duration: number; // milliseconds
}
```

**Option B: Web Speech API + Manual Alignment**
```typescript
// Web Speech API doesn't provide timestamps
// So we need to align manually or use Transcription as reference

// 1. Get transcription chunks (reference)
const transcriptionChunks = await getTranscriptionChunks(videoId);

// 2. User uses Speech To Text
const speechText = await webSpeechAPI.recognize(audio);

// 3. Map using fuzzy matching + time hints
const mappedSegments = await fuzzyMapWithTimeHints(
  speechText,
  transcriptionChunks
);
```

---

### Scenario 3: Mixed (แก้ไขบางส่วน + พิมพ์ใหม่บางส่วน)

**แนะนำ: Hybrid Approach (Approach 4)**

**Implementation Flow:**

```typescript
async function mapDocumentToTimestamps(
  document: Document,
  transcription?: TranscriptionResult
): Promise<DocumentMapping> {
  const mappings: TextMapping[] = [];
  
  // 1. If has transcription: Use diff algorithm for overlapping parts
  if (transcription) {
    const diffMappings = await diffBasedMapping(
      document.content,
      transcription.fullText,
      transcription.chunks
    );
    mappings.push(...diffMappings);
  }
  
  // 2. Use manual time tags (if exist)
  if (document.timeTags) {
    const manualMappings = createMappingsFromTimeTags(
      document.content,
      document.timeTags
    );
    mappings.push(...manualMappings);
  }
  
  // 3. Use speech timestamps (if exist)
  if (document.speechSegments) {
    const speechMappings = createMappingsFromSpeech(
      document.content,
      document.speechSegments
    );
    mappings.push(...speechMappings);
  }
  
  // 4. Interpolate for unmapped sections
  const interpolated = interpolateUnmappedSections(
    document.content,
    mappings
  );
  
  return {
    documentId: document.id,
    transcriptionId: transcription?.id,
    content: document.content,
    mappings: [...mappings, ...interpolated]
  };
}
```

---

## 🎯 Implementation Plan

### Phase 1: Manual Time Tagging (MVP)

**Goal:** รองรับกรณี User พิมพ์ใหม่ทั้งหมด

**Tasks:**
1. ✅ เพิ่ม Time Tagging UI ใน Document Editor
2. ✅ เก็บ time tags ใน document metadata
3. ✅ Search API ใช้ time tags สำหรับ timestamp lookup
4. ✅ Display timestamps ใน search results

**UI Design:**
```
[Document Editor]
┌─────────────────────────────────────┐
│ Text: "คำพูดของผู้ประชุม..."        │
│       [Tag: 00:05:23]              │
└─────────────────────────────────────┘

[Video Player]
┌─────────────────────────────────────┐
│ [▶] 00:05:23 / 01:30:00            │
│                                     │
│ [Video Player]                      │
└─────────────────────────────────────┘
```

**User Flow:**
1. User เลือก text ใน document
2. Click "Tag Time" button
3. เลือก timestamp จาก video player
4. หรือ Play video และ Type (auto-tag)

---

### Phase 2: Speech To Text Integration

**Goal:** รองรับ Speech To Text พร้อม timestamps

**Tasks:**
1. ✅ Integrate Speech API (Azure/Google Cloud)
2. ✅ Extract timestamps from Speech API
3. ✅ Align with video timestamps
4. ✅ Store speech segments in document

---

### Phase 3: Fuzzy Matching (Optional)

**Goal:** Auto-map สำหรับส่วนที่แก้ไข/พิมพ์ใหม่

**Tasks:**
1. ✅ Implement fuzzy matching algorithm
2. ✅ Semantic similarity (optional, using NLP)
3. ✅ Confidence scoring
4. ✅ Interpolation for unmapped sections

---

## 📐 Data Model

### Document with Time Mapping

```typescript
interface Document {
  id: string;
  content: string;
  transcriptionId?: string; // Reference to original transcription
  
  // Time mapping metadata
  timeMapping: {
    // Manual time tags
    timeTags?: TimeTag[];
    
    // Speech To Text segments
    speechSegments?: SpeechSegment[];
    
    // Auto-mapped segments (from diff/fuzzy)
    autoMapped?: AutoMappedSegment[];
    
    // Mapping version (for cache invalidation)
    mappingVersion: number;
  };
}

interface TimeTag {
  id: string;
  documentStart: number; // Character position
  documentEnd: number;
  videoStartTime: number; // Seconds
  videoEndTime: number;
  source: 'manual' | 'speech' | 'auto';
  createdAt: Date;
  createdBy: string;
}

interface AutoMappedSegment {
  documentStart: number;
  documentEnd: number;
  chunkId?: string;
  videoStartTime: number;
  videoEndTime: number;
  confidence: number;
  matchType: 'exact' | 'fuzzy' | 'semantic';
}
```

### Database Schema

```sql
-- Time Tags Table
CREATE TABLE document_time_tags (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Document position
    document_start INTEGER NOT NULL,
    document_end INTEGER NOT NULL,
    
    -- Video timestamp
    video_start_time DECIMAL(10,2) NOT NULL, -- seconds
    video_end_time DECIMAL(10,2) NOT NULL,
    
    -- Metadata
    source VARCHAR(20) NOT NULL, -- 'manual', 'speech', 'auto'
    confidence DECIMAL(3,2), -- 0.00-1.00
    
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_document_time_tags_document_id ON document_time_tags(document_id),
    INDEX idx_document_time_tags_video_time ON document_time_tags(video_start_time, video_end_time)
);

-- Speech Segments Table (if using Speech To Text)
CREATE TABLE document_speech_segments (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Document position
    document_start INTEGER NOT NULL,
    document_end INTEGER NOT NULL,
    
    -- Speech API timestamp
    speech_start_time DECIMAL(10,2) NOT NULL, -- milliseconds or seconds
    speech_end_time DECIMAL(10,2) NOT NULL,
    
    -- Video timestamp (aligned)
    video_start_time DECIMAL(10,2) NOT NULL,
    video_end_time DECIMAL(10,2) NOT NULL,
    
    -- Metadata
    speech_api VARCHAR(50), -- 'azure', 'google', 'web_speech'
    confidence DECIMAL(3,2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 🔍 Search Implementation

### Search with Time Mapping

```typescript
async function searchWithTimestamps(
  documentId: string,
  searchQuery: string
): Promise<SearchResult[]> {
  // 1. Get document
  const document = await getDocument(documentId);
  
  // 2. Get time mapping
  const timeMapping = await getDocumentTimeMapping(documentId);
  
  // 3. Search in document text
  const textMatches = findTextMatches(document.content, searchQuery);
  
  // 4. Map to timestamps
  const results: SearchResult[] = textMatches.map(match => {
    // Priority: Manual tags > Speech timestamps > Auto-mapped > Interpolated
    
    // Try manual time tags first
    const manualTag = findTimeTagForRange(
      timeMapping.timeTags,
      match.start,
      match.end
    );
    if (manualTag) {
      return {
        text: match.text,
        startTime: manualTag.videoStartTime,
        endTime: manualTag.videoEndTime,
        confidence: 1.0,
        source: 'manual'
      };
    }
    
    // Try speech segments
    const speechSegment = findSpeechSegmentForRange(
      timeMapping.speechSegments,
      match.start,
      match.end
    );
    if (speechSegment) {
      return {
        text: match.text,
        startTime: speechSegment.videoStartTime,
        endTime: speechSegment.videoEndTime,
        confidence: speechSegment.confidence || 0.8,
        source: 'speech'
      };
    }
    
    // Try auto-mapped
    const autoMapped = findAutoMappedForRange(
      timeMapping.autoMapped,
      match.start,
      match.end
    );
    if (autoMapped) {
      return {
        text: match.text,
        startTime: autoMapped.videoStartTime,
        endTime: autoMapped.videoEndTime,
        confidence: autoMapped.confidence,
        source: 'auto'
      };
    }
    
    // Fallback: Interpolate
    const interpolated = interpolateTimestamp(
      match.start,
      timeMapping
    );
    return {
      text: match.text,
      startTime: interpolated.startTime,
      endTime: interpolated.endTime,
      confidence: 0.5,
      source: 'interpolated'
    };
  });
  
  return results;
}
```

---

## 🎨 UI/UX Design

### Document Editor with Time Tagging

```typescript
// Component: DocumentEditorWithTimeTags
interface DocumentEditorWithTimeTagsProps {
  document: Document;
  videoUrl: string;
  transcription?: TranscriptionResult;
  onSave: (document: Document) => void;
}

function DocumentEditorWithTimeTags({
  document,
  videoUrl,
  transcription,
  onSave
}) {
  const [selectedText, setSelectedText] = useState<string>('');
  const [selectedRange, setSelectedRange] = useState<Range | null>(null);
  const [videoTime, setVideoTime] = useState<number>(0);
  
  // Time tagging handler
  const handleTagTime = () => {
    if (selectedRange) {
      const timeTag: TimeTag = {
        documentStart: selectedRange.startOffset,
        documentEnd: selectedRange.endOffset,
        videoStartTime: videoTime,
        videoEndTime: videoTime + 5, // Default 5 seconds
        source: 'manual'
      };
      
      // Add to document
      document.timeTags.push(timeTag);
      onSave(document);
    }
  };
  
  // Play & Type mode
  const [playAndTypeMode, setPlayAndTypeMode] = useState(false);
  
  useEffect(() => {
    if (playAndTypeMode) {
      // Auto-tag with current video time when user types
      const handleInput = () => {
        const cursorPosition = editor.getCursorPosition();
        const timeTag: TimeTag = {
          documentStart: cursorPosition,
          documentEnd: cursorPosition,
          videoStartTime: videoTime,
          videoEndTime: videoTime,
          source: 'manual'
        };
        document.timeTags.push(timeTag);
      };
      
      editor.on('input', handleInput);
      return () => editor.off('input', handleInput);
    }
  }, [playAndTypeMode, videoTime]);
  
  return (
    <div className="document-editor-with-timestamps">
      <div className="editor-panel">
        <DocumentEditor
          content={document.content}
          onSelectionChange={(range) => {
            setSelectedRange(range);
            setSelectedText(editor.getSelectedText());
          }}
        />
        
        {selectedText && (
          <Button onClick={handleTagTime}>
            Tag Time: {formatTime(videoTime)}
          </Button>
        )}
        
        <Toggle
          label="Play & Type Mode"
          checked={playAndTypeMode}
          onChange={setPlayAndTypeMode}
        />
      </div>
      
      <div className="video-panel">
        <VideoPlayer
          url={videoUrl}
          onTimeUpdate={setVideoTime}
        />
        
        {/* Show time tags on video timeline */}
        <TimeTagTimeline
          timeTags={document.timeTags}
          onTimeTagClick={(tag) => {
            editor.setCursorPosition(tag.documentStart);
            videoPlayer.seek(tag.videoStartTime);
          }}
        />
      </div>
    </div>
  );
}
```

---

## 📊 เปรียบเทียบกรณีต่างๆ

| Scenario | Approach | Accuracy | UX Effort |
|----------|----------|----------|-----------|
| **ใช้ Transcription (แก้ไข)** | Diff Algorithm | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **พิมพ์ใหม่ทั้งหมด** | Manual Tagging | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Speech To Text** | Speech API Timestamps | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Mixed** | Hybrid | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## ✅ สรุปและคำแนะนำ

### สำหรับกรณีของคุณ (ไม่สนใจ Order Change)

**แนะนำ: Hybrid Approach (Approach 4)**

**Strategy:**

1. **ถ้ามี Transcription Reference:**
   - ใช้ Diff Algorithm สำหรับส่วนที่แก้ไข
   - Map กลับไปยัง chunks/timestamps

2. **ถ้าไม่มี Transcription หรือพิมพ์ใหม่:**
   - **Manual Time Tagging** (แนะนำ)
   - หรือ **Speech To Text with Timestamps** (ถ้ามี Speech API)

3. **Search Implementation:**
   - Priority: Manual tags > Speech timestamps > Auto-mapped
   - Fallback: Interpolation สำหรับส่วนที่ไม่มี mapping

### Implementation Priority

**Phase 1: Manual Time Tagging (MVP)**
- ✅ เพิ่ม Time Tagging UI
- ✅ เก็บ time tags
- ✅ Search with timestamps

**Phase 2: Speech To Text (ถ้ามี)**
- ✅ Integrate Speech API
- ✅ Extract timestamps

**Phase 3: Auto-mapping (Optional)**
- ✅ Fuzzy matching สำหรับส่วนที่แก้ไข

---

## 📝 Example Usage

### Manual Time Tagging

```typescript
// User flow:
// 1. User opens document editor
// 2. Selects text: "คำพูดของผู้ประชุม"
// 3. Clicks "Tag Time" button
// 4. Video player shows current time: 00:05:23
// 5. Time tag is created:
{
  documentStart: 100,
  documentEnd: 120,
  videoStartTime: 323, // 5 minutes 23 seconds
  videoEndTime: 328,
  source: 'manual'
}

// 6. When searching:
search("คำพูดของผู้ประชุม")
// → Returns: { text: "...", timestamp: 323, confidence: 1.0 }
```

### Play & Type Mode

```typescript
// User flow:
// 1. User enables "Play & Type Mode"
// 2. Video plays at 00:05:23
// 3. User types: "คำพูดของผู้ประชุม"
// 4. Auto-tag created:
{
  documentStart: 100,
  documentEnd: 120,
  videoStartTime: 323,
  videoEndTime: 323,
  source: 'manual'
}
```

---

---

## 📍 Implementation Location

**สำหรับกรณีนี้ (พิมพ์ใหม่/Speech To Text):**

### ✅ **Senate-Backend** (ต้อง Implement)
- Manual Time Tagging API
- Speech To Text Integration (ถ้ามี)
- Search with Time Tags

### ✅ **Transcription Service** (ไม่ต้องแก้ไข)
- ใช้ API ที่มีอยู่แล้ว: `GET /transcription/{task_id}/chunks`

### ❌ **File Service** (ไม่เกี่ยวข้อง)

**ดูรายละเอียดเพิ่มเติม:** [DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md](./DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md)

---

**Last Updated**: 2024-12-05  
**Status**: Advanced Analysis Complete ✅

