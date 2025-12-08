# 📊 การวิเคราะห์: การ Map ข้อความที่แก้ไขกลับไปยัง Video Timestamps

**วันที่สร้าง**: 2024-12-05  
**Purpose**: วิเคราะห์แนวทางการ map ข้อความที่ User แก้ไขกลับไปยัง Transcription Chunks และ Video Timestamps

---

## 📋 ปัญหา (Problem Statement)

### สถานการณ์ปัจจุบัน

1. **Transcription Service** แปลง Media (audio/video) → Text (Chunks with timestamps)
2. **User** แก้ไขข้อความที่ Transcription ไว้ → Document Text (edited)
3. **Search System** (S0303) ต้องการค้นหาและรู้ว่า:
   - ข้อความที่ค้นเจออยู่ในช่วงเวลาไหนในวีดิโอ
   - สามารถ jump to video timestamp ได้

### ความท้าทาย

- ❌ **ข้อความที่ User แก้ไข ≠ ข้อความต้นฉบับจาก Transcription**
- ❌ **จำนวนคำ/ตัวอักษรเปลี่ยน** (เพิ่ม/ลบ/แก้ไข)
- ❌ **ลำดับข้อความอาจเปลี่ยน** (ย้ายประโยค/ย่อหน้า)
- ❌ **ต้อง map กลับไปยัง original chunks และ timestamps**

---

## 💡 แนวทางที่เสนอ (Character/Word Count Based)

### หลักการ

```
Original Transcription (5,000 chars) → User Edited (5,500 chars)
Chunk 1: 0-2min (500 chars) → Map to edited document (0-550 chars)
Chunk 2: 2-4min (600 chars) → Map to edited document (550-1210 chars)
...
```

### ข้อดี
- ✅ เรียบง่าย: ใช้อัตราส่วน (ratio) ในการ map
- ✅ ไม่ต้องเก็บข้อมูลเพิ่มมาก

### ข้อเสีย
- ❌ **ไม่แม่นยำ**: ถ้า User เพิ่ม/ลบข้อความมาก
- ❌ **ไม่รองรับการย้ายลำดับ**: ถ้า User ย้ายประโยค/ย่อหน้า
- ❌ **Error Accumulation**: ข้อผิดพลาดสะสมไปเรื่อยๆ (drift)
- ❌ **ไม่รองรับการแก้ไขที่ซับซ้อน**: แทนที่ประโยค, ย่อหน้า

---

## 🎯 แนวทางที่แนะนำ (Multiple Approaches)

### **Approach 1: Character-Based Mapping with Anchors (แนะนำ)**

#### หลักการ
- ใช้ **anchor points** (จุดอ้างอิง) ที่แก้ไขน้อย
- คำนวณ offset สำหรับแต่ละ chunk
- ใช้ fuzzy matching สำหรับส่วนที่แก้ไขมาก

#### Implementation

```typescript
interface ChunkMapping {
  originalChunkId: string;
  originalText: string;
  originalStartTime: number;
  originalEndTime: number;
  originalCharOffset: number;
  originalCharLength: number;
  
  editedText: string;
  editedCharOffset: number;
  editedCharLength: number;
  
  confidence: number; // 0-1 (ความมั่นใจในการ map)
}

// Algorithm:
// 1. Split original text into chunks (ตาม timestamps)
// 2. Find best match for each chunk in edited text
// 3. Calculate character offset adjustment
// 4. Store mapping table
```

#### ข้อดี
- ✅ แม่นยำกว่า character count อย่างเดียว
- ✅ รองรับการแก้ไขที่ไม่มาก
- ✅ สามารถปรับปรุงได้ด้วย fuzzy matching

#### ข้อเสีย
- ⚠️ ต้องเก็บ mapping table
- ⚠️ อาจไม่แม่นยำถ้าแก้ไขมาก

---

### **Approach 2: Word-Level Diff with Timestamps (แนะนำที่สุด)**

#### หลักการ
- ใช้ **Word-level diff algorithm** (LCS, Myers diff)
- Map แต่ละคำกลับไปยัง original chunk
- เก็บ timestamp สำหรับแต่ละคำ (word-level timestamps)

#### Implementation

```typescript
interface WordTimestamp {
  word: string;
  startTime: number;
  endTime: number;
  chunkId: string;
  wordIndex: number;
}

interface DocumentMapping {
  documentId: string;
  transcriptionId: string;
  wordMappings: WordMapping[];
}

interface WordMapping {
  originalWord: WordTimestamp;
  editedWord: {
    text: string;
    position: number; // position in edited document
  };
  operation: 'unchanged' | 'inserted' | 'deleted' | 'modified';
  confidence: number;
}

// Algorithm (Simplified):
// 1. Extract word-level timestamps from transcription chunks
// 2. Create word sequence with timestamps
// 3. Apply diff algorithm (Myers diff) between original and edited
// 4. Map each word in edited text to original word + timestamp
```

#### ข้อดี
- ✅ **แม่นยำมาก**: ใช้ word-level mapping
- ✅ **รองรับการแก้ไขทุกประเภท**: เพิ่ม/ลบ/แก้ไข/ย้าย
- ✅ **แม่นยำแม้แก้ไขมาก**: diff algorithm จัดการได้ดี
- ✅ **รองรับการย้ายลำดับ**: สามารถ track ได้

#### ข้อเสีย
- ⚠️ ต้องเก็บ word-level timestamps (storage เพิ่มขึ้น)
- ⚠️ Algorithm ซับซ้อนขึ้น

---

### **Approach 3: Hybrid: Chunk + Word Anchors**

#### หลักการ
- ใช้ **chunk-level mapping** เป็นหลัก
- ใช้ **word anchors** สำหรับส่วนที่แก้ไขมาก
- Combine ทั้งสองวิธี

#### Implementation

```typescript
interface HybridMapping {
  // Chunk-level mapping (fast lookup)
  chunkMappings: ChunkMapping[];
  
  // Word-level anchors (high-precision areas)
  wordAnchors: WordAnchor[];
}

interface WordAnchor {
  originalWord: string;
  editedWord: string;
  timestamp: number;
  chunkId: string;
  // Used as reference points for interpolation
}
```

#### ข้อดี
- ✅ **สมดุลระหว่างแม่นยำและประสิทธิภาพ**
- ✅ Storage ไม่มาก (เก็บแค่ anchors)
- ✅ Query เร็ว (chunk-level lookup)

#### ข้อเสีย
- ⚠️ อาจไม่แม่นยำเท่า word-level

---

## 📊 เปรียบเทียบแนวทาง

| Aspect | Character Count | Chunk + Anchors | Word-Level Diff | Hybrid |
|--------|----------------|-----------------|-----------------|--------|
| **Accuracy** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Storage** | ✅ ต่ำมาก | ✅ ต่ำ | ⚠️ สูง | ✅ ปานกลาง |
| **Performance** | ✅ เร็วมาก | ✅ เร็ว | ⚠️ ช้า | ✅ เร็ว |
| **Complexity** | ✅ ง่ายมาก | ⚠️ ปานกลาง | ❌ ซับซ้อน | ⚠️ ปานกลาง |
| **Edit Support** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Order Change** | ❌ ไม่รองรับ | ⚠️ รองรับบางส่วน | ✅ รองรับเต็ม | ⚠️ รองรับบางส่วน |

---

## ✅ คำแนะนำ

### **สำหรับ Production: Approach 2 (Word-Level Diff) หรือ Approach 3 (Hybrid)**

#### เหตุผล

1. **แม่นยำ**: User อาจแก้ไขมาก (เพิ่ม/ลบ/แก้ไข)
2. **รองรับทุกกรณี**: รวมถึงการย้ายลำดับ
3. **Scalable**: สามารถปรับปรุง accuracy ได้

#### Implementation Strategy

**Phase 1: Basic Implementation (Hybrid)**
```typescript
// 1. Store transcription chunks with word-level timestamps
interface TranscriptionChunk {
  chunkId: string;
  startTime: number;
  endTime: number;
  text: string;
  words: WordTimestamp[]; // word-level timestamps
}

// 2. When user edits document:
// - Calculate diff between original and edited
// - Map each word to original word + timestamp
// - Store mapping table

// 3. For search:
// - Find matched text in edited document
// - Look up timestamp from mapping
// - Return timestamp range
```

**Phase 2: Enhanced (Full Word-Level Diff)**
- Implement full word-level diff
- Handle complex edits (sentence reordering)
- Improve accuracy with fuzzy matching

---

## 🏗️ Architecture

### Data Model

```typescript
// 1. Transcription Result (existing)
interface TranscriptionResult {
  transcriptionId: string;
  chunks: TranscriptionChunk[];
  fullText: string;
}

// 2. Document (edited by user)
interface Document {
  documentId: string;
  transcriptionId: string; // Reference to original
  content: string; // Edited text
  version: number;
  lastEditedAt: Date;
}

// 3. Word Mapping (NEW - for search)
interface DocumentWordMapping {
  documentId: string;
  wordMappings: WordMapping[];
  mappingVersion: number;
  createdAt: Date;
  // Index for fast lookup
  wordIndex: Map<string, WordMapping[]>; // word → mappings
}
```

### Storage Strategy

**Option A: Store in PostgreSQL**
```sql
CREATE TABLE transcription.document_word_mappings (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL,
    transcription_id VARCHAR(100) NOT NULL,
    
    -- Word mapping data (JSONB for flexibility)
    word_mappings JSONB NOT NULL,
    
    -- Index metadata
    mapping_version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (transcription_id) REFERENCES transcription_results(transcription_id)
);

-- Index for fast word lookup
CREATE INDEX idx_document_word_mappings_document_id ON transcription.document_word_mappings(document_id);
CREATE INDEX idx_document_word_mappings_words_gin ON transcription.document_word_mappings USING gin(word_mappings);
```

**Option B: Store in Document Service (Hybrid)**
- Store mapping in document metadata
- Use PostgreSQL JSONB column
- Index for search performance

---

## 🔍 Search Implementation

### Search Flow

```
User searches for "คำค้นหา"
    ↓
Search in Document Text (edited)
    ↓
Find matches in edited text
    ↓
Look up WordMapping for matched words
    ↓
Get timestamps from original transcription
    ↓
Return results with video timestamps
```

### Example

```typescript
async function searchWithTimestamps(
  documentId: string,
  searchQuery: string
): Promise<SearchResult[]> {
  // 1. Get document content
  const document = await getDocument(documentId);
  
  // 2. Get word mappings
  const mappings = await getDocumentWordMappings(documentId);
  
  // 3. Search in edited text
  const matches = findTextMatches(document.content, searchQuery);
  
  // 4. Map to timestamps
  const results: SearchResult[] = matches.map(match => {
    const wordMappings = findWordMappingsForRange(
      mappings,
      match.startPosition,
      match.endPosition
    );
    
    return {
      text: match.text,
      startTime: wordMappings[0]?.timestamp || 0,
      endTime: wordMappings[wordMappings.length - 1]?.timestamp || 0,
      chunkIds: wordMappings.map(w => w.chunkId),
      confidence: calculateConfidence(wordMappings)
    };
  });
  
  return results;
}
```

---

## 📈 Performance Considerations

### Optimization Strategies

1. **Caching**
   - Cache word mappings for frequently accessed documents
   - Use Redis for hot documents

2. **Lazy Loading**
   - Calculate mappings on-demand (when first search)
   - Background job for pre-calculation

3. **Incremental Updates**
   - Only recalculate mappings for changed sections
   - Use diff to identify changed ranges

4. **Indexing**
   - Use PostgreSQL GIN index for JSONB word mappings
   - Full-text search index for document content

---

## 🎯 Implementation Plan

### Phase 1: Basic Word-Level Mapping (MVP)

**Tasks:**
1. ✅ Add word-level timestamps to TranscriptionChunk
2. ✅ Create DocumentWordMapping table/model
3. ✅ Implement basic diff algorithm (word-level)
4. ✅ Store mappings when document is edited
5. ✅ Basic search with timestamp lookup

**Duration:** 2-3 weeks

---

### Phase 2: Enhanced Mapping (Production)

**Tasks:**
1. ✅ Improve diff algorithm (handle reordering)
2. ✅ Add confidence scoring
3. ✅ Performance optimization (caching, indexing)
4. ✅ UI integration (show timestamps in search results)

**Duration:** 2-3 weeks

---

### Phase 3: Advanced Features

**Tasks:**
1. ✅ Visual diff highlighting
2. ✅ Manual mapping correction (admin tool)
3. ✅ Batch processing for existing documents
4. ✅ Analytics and reporting

**Duration:** 2-3 weeks

---

## 📝 สรุป

### คำแนะนำสุดท้าย

**ไม่แนะนำใช้ Character Count Based** เพราะ:
- ❌ ไม่แม่นยำพอ
- ❌ Error accumulation
- ❌ ไม่รองรับการแก้ไขที่ซับซ้อน

**แนะนำใช้ Word-Level Diff** เพราะ:
- ✅ แม่นยำมาก
- ✅ รองรับทุกกรณีการแก้ไข
- ✅ Scalable และ maintainable

**Alternative: Hybrid Approach** สำหรับเริ่มต้น:
- ใช้ chunk-level เป็นหลัก
- เพิ่ม word anchors สำหรับส่วนสำคัญ
- พัฒนาเป็น word-level เมื่อพร้อม

---

## 🔗 Related Documents

- [Transcription Metrics Analysis](./TRANSCRIPTION_METRICS_ANALYSIS.md)
- [Staging Architecture](./STAGING_VPN_ARCHITECTURE.md)

---

**Last Updated**: 2024-12-05  
**Status**: Analysis Complete ✅

