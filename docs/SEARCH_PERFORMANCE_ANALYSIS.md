# 📊 การวิเคราะห์ประสิทธิภาพ: Document Search & Mapping Service

**วันที่สร้าง**: 2024-12-05  
**Purpose**: วิเคราะห์ประสิทธิภาพการค้นหาและ Mapping Service สำหรับ 50-300 เอกสาร

---

## 📋 สถานการณ์

### Scale
- **50 เอกสาร** ที่ต้อง Mapping Service (active editing)
- **200-300 เอกสาร** สำหรับการค้นหา (search corpus)

### คำถาม
1. การค้นหาข้อความใน Text ไฟล์จะยากเกินไปหรือใช้เวลานานไหม?
2. ควรใช้ Vector Database หรือเครื่องมืออื่นๆ ช่วยไหม?

---

## 🔍 การวิเคราะห์ประสิทธิภาพ

### Scenario 1: Full-Text Search (PostgreSQL/Elasticsearch)

#### PostgreSQL Full-Text Search

**Performance:**
```sql
-- Index: GIN index on text content
CREATE INDEX idx_documents_content_gin ON documents 
USING gin(to_tsvector('thai', content));

-- Search query
SELECT * FROM documents 
WHERE to_tsvector('thai', content) @@ plainto_tsquery('thai', 'คำค้นหา')
LIMIT 20;
```

**Benchmark (ประมาณ):**
- **50 เอกสาร**: ~5-10ms per query ✅
- **300 เอกสาร**: ~20-50ms per query ✅
- **1,000 เอกสาร**: ~50-100ms per query ⚠️
- **10,000 เอกสาร**: ~200-500ms per query ❌

**ข้อดี:**
- ✅ Fast สำหรับ corpus ขนาดเล็ก-กลาง (< 1,000 docs)
- ✅ Exact matching (keyword search)
- ✅ No additional infrastructure needed

**ข้อเสีย:**
- ⚠️ ช้าเมื่อ corpus ใหญ่ (> 10,000 docs)
- ⚠️ ไม่รองรับ Semantic Search (ความหมาย)
- ⚠️ Thai language support อาจไม่ดีเท่า Vector Search

---

#### Elasticsearch (Advanced Full-Text Search)

**Performance:**
```
GET /documents/_search
{
  "query": {
    "match": {
      "content": "คำค้นหา"
    }
  },
  "size": 20
}
```

**Benchmark (ประมาณ):**
- **50 เอกสาร**: ~10-20ms per query ✅
- **300 เอกสาร**: ~30-60ms per query ✅
- **10,000 เอกสาร**: ~100-200ms per query ✅
- **100,000 เอกสาร**: ~200-500ms per query ✅

**ข้อดี:**
- ✅ Very fast (even for large corpus)
- ✅ Advanced features (fuzzy, synonyms, highlighting)
- ✅ Thai language analyzer (ik analyzer)

**ข้อเสีย:**
- ⚠️ Additional infrastructure needed
- ⚠️ Memory/CPU usage สูงกว่า PostgreSQL

---

### Scenario 2: Vector Database (Semantic Search)

#### Vector Search with Embeddings

**Architecture:**
```
Document Content → Embedding Model → Vector (768/1536 dimensions)
    ↓
Store in Vector DB (Pinecone, Qdrant, Weaviate, pgvector)
    ↓
Search: Query → Embedding → Vector Similarity Search
```

**Performance:**
```
Query: "คำค้นหา" → Embedding Vector → Cosine Similarity
```

**Benchmark (ประมาณ):**
- **50 เอกสาร**: ~50-100ms per query (รวม embedding) ⚠️
- **300 เอกสาร**: ~100-200ms per query ⚠️
- **10,000 เอกสาร**: ~200-300ms per query ✅
- **100,000+ เอกสาร**: ~300-500ms per query ✅✅

**ข้อดี:**
- ✅ **Semantic Search**: หาได้แม้คำไม่ตรงกัน (ความหมายใกล้เคียง)
- ✅ **Scalable**: ดีมากสำหรับ corpus ใหญ่
- ✅ **Multilingual**: ทำงานได้หลายภาษา

**ข้อเสีย:**
- ❌ **Overkill** สำหรับ corpus ขนาดเล็ก (< 1,000 docs)
- ❌ **Complexity**: ต้องมี Embedding Model + Vector DB
- ❌ **Cost**: Additional infrastructure + processing
- ❌ **Latency**: ต้อง generate embedding ก่อน search

---

## 📊 เปรียบเทียบประสิทธิภาพ

### สำหรับ 200-300 เอกสาร

| Method | Query Time | Setup Complexity | Semantic Search | Recommendation |
|--------|-----------|------------------|-----------------|----------------|
| **PostgreSQL FTS** | 20-50ms | ⭐ (Simple) | ❌ | ✅ **แนะนำ** |
| **Elasticsearch** | 30-60ms | ⭐⭐⭐ (Medium) | ⚠️ (Limited) | ✅ ถ้าต้องการ advanced features |
| **Vector DB** | 100-200ms | ⭐⭐⭐⭐⭐ (Complex) | ✅ | ⚠️ **Overkill** สำหรับขนาดนี้ |

---

## ✅ คำแนะนำสำหรับกรณีของคุณ (200-300 เอกสาร)

### **Approach 1: PostgreSQL Full-Text Search (แนะนำ)**

#### เหตุผล
- ✅ **Fast enough**: 20-50ms สำหรับ 300 เอกสาร
- ✅ **Simple**: ไม่ต้องเพิ่ม infrastructure
- ✅ **Cost-effective**: ใช้ database ที่มีอยู่แล้ว
- ✅ **Thai Support**: PostgreSQL รองรับ Thai FTS

#### Implementation

```sql
-- 1. Enable Thai full-text search (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 2. Create full-text index
CREATE INDEX idx_documents_content_fts ON documents 
USING gin(to_tsvector('thai', content));

-- 3. Create trigram index for fuzzy matching
CREATE INDEX idx_documents_content_trgm ON documents 
USING gin(content gin_trgm_ops);

-- 4. Search query
SELECT 
    id,
    content,
    ts_rank(to_tsvector('thai', content), plainto_tsquery('thai', $1)) AS rank,
    -- Highlight matches
    ts_headline('thai', content, plainto_tsquery('thai', $1)) AS highlighted
FROM documents
WHERE 
    to_tsvector('thai', content) @@ plainto_tsquery('thai', $1)
    OR content ILIKE '%' || $1 || '%' -- Fallback for exact match
ORDER BY rank DESC
LIMIT 20;
```

**Performance:**
- **Query time**: 20-50ms สำหรับ 300 เอกสาร ✅
- **Concurrent queries**: 10-20 queries/second ✅

---

### **Approach 2: Hybrid (Full-Text + Lightweight Vector) - ถ้าต้องการ Semantic Search**

#### หลักการ
- ใช้ **Full-Text Search** เป็น primary (fast, exact match)
- ใช้ **Lightweight Embedding** สำหรับ semantic search (optional)
- ไม่ต้องใช้ Vector DB แยก → เก็บ vector ใน PostgreSQL (pgvector)

#### Implementation

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector column
ALTER TABLE documents ADD COLUMN embedding vector(384); -- Use smaller model (all-MiniLM-L6-v2)

-- Create index
CREATE INDEX idx_documents_embedding ON documents 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Hybrid search
WITH fulltext_results AS (
    SELECT id, content, ts_rank(...) AS fts_rank
    FROM documents
    WHERE to_tsvector('thai', content) @@ plainto_tsquery('thai', $1)
    LIMIT 10
),
vector_results AS (
    SELECT id, content, 1 - (embedding <=> $2::vector) AS similarity
    FROM documents
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $2::vector
    LIMIT 10
)
SELECT DISTINCT * FROM (
    SELECT * FROM fulltext_results
    UNION
    SELECT * FROM vector_results
) combined
ORDER BY COALESCE(fts_rank, 0) + COALESCE(similarity, 0) DESC
LIMIT 20;
```

**ข้อดี:**
- ✅ Fast full-text search (primary)
- ✅ Semantic search (fallback)
- ✅ ใช้ PostgreSQL เดียว (ไม่ต้อง Vector DB แยก)

**ข้อเสีย:**
- ⚠️ ต้อง generate embeddings (อาจช้า)
- ⚠️ เพิ่ม complexity

---

### **Approach 3: Elasticsearch (ถ้า corpus จะโตเร็ว)**

#### เหตุผล
- ถ้า corpus จะโตถึง **1,000+ เอกสาร** ในอนาคต
- ต้องการ **advanced features** (highlighting, faceted search, etc.)

#### Implementation

```typescript
// Elasticsearch setup
const client = new Client({
  node: 'http://localhost:9200'
});

// Index document
await client.index({
  index: 'documents',
  id: documentId,
  document: {
    content: documentContent,
    mediaId: mediaId,
    transcriptionId: transcriptionId,
    createdAt: new Date()
  }
});

// Search
const result = await client.search({
  index: 'documents',
  body: {
    query: {
      match: {
        content: {
          query: searchQuery,
          fuzziness: 'AUTO',
          operator: 'and'
        }
      }
    },
    highlight: {
      fields: {
        content: {}
      }
    }
  }
});
```

**Performance:**
- **Query time**: 30-60ms สำหรับ 300 เอกสาร ✅
- **Scalable**: ดีมากเมื่อ corpus โต

---

## 🔧 Mapping Service Performance

### สำหรับ 50 เอกสารที่ต้อง Mapping

#### Current Approach (Word-level Mapping)

**Performance Analysis:**
```typescript
// Mapping algorithm complexity
// Document length: ~5,000 words
// Transcription chunks: ~100 chunks
// Processing time per document: ~2-5 seconds

// 50 documents × 3 seconds = 150 seconds (2.5 minutes)
// Sequential processing: ❌ ช้าเกินไป

// Parallel processing (10 workers):
// 50 documents ÷ 10 = 5 batches
// 5 batches × 3 seconds = 15 seconds ✅
```

**Optimization:**

1. **Parallel Processing**
   ```typescript
   // Process multiple documents in parallel
   const workers = 10; // Configurable
   const batches = chunkArray(documents, workers);
   
   await Promise.all(
     batches.map(batch => 
       Promise.all(batch.map(doc => processMapping(doc)))
     )
   );
   ```

2. **Incremental Mapping**
   ```typescript
   // Only process changed sections (not entire document)
   const changedSections = diff(document, lastVersion);
   await processMappingIncremental(documentId, changedSections);
   ```

3. **Background Job Queue**
   ```typescript
   // Queue mapping jobs (rate limiting)
   await mappingQueue.enqueue({
     documentId,
     priority: 'normal'
   });
   ```

---

## 📊 Performance Summary

### Search Performance (200-300 เอกสาร)

| Method | Query Time | Setup | Semantic | Recommendation |
|--------|-----------|-------|----------|----------------|
| **PostgreSQL FTS** | 20-50ms | ⭐ | ❌ | ✅ **แนะนำ** |
| **Elasticsearch** | 30-60ms | ⭐⭐⭐ | ⚠️ | ✅ ถ้าโตเร็ว |
| **Vector DB** | 100-200ms | ⭐⭐⭐⭐⭐ | ✅ | ❌ Overkill |

**สรุป: PostgreSQL Full-Text Search เพียงพอสำหรับ 200-300 เอกสาร** ✅

---

### Mapping Service Performance (50 เอกสาร)

| Approach | Total Time | CPU Usage | Recommendation |
|----------|-----------|-----------|----------------|
| **Sequential** | ~2.5 min | 100% | ❌ |
| **Parallel (10 workers)** | ~15 sec | 100% | ✅ |
| **Background Queue** | ~15 sec | 50% | ✅✅ |

**สรุป: ใช้ Parallel Processing + Background Queue** ✅

---

## 🎯 แนวทางที่แนะนำ

### Phase 1: PostgreSQL Full-Text Search (MVP)

**Why:**
- ✅ Fast enough (20-50ms) สำหรับ 300 เอกสาร
- ✅ Simple setup
- ✅ Cost-effective

**Implementation:**
1. เพิ่ม GIN index สำหรับ full-text search
2. Implement search API
3. Support Thai language

---

### Phase 2: Optimize Mapping Service

**Why:**
- 50 เอกสารต้อง mapping → ใช้เวลา 2.5 นาที (sequential)
- ต้อง optimize ด้วย parallel processing

**Implementation:**
1. Background job queue (RabbitMQ/Celery)
2. Parallel processing (10 workers)
3. Incremental mapping (เฉพาะส่วนที่เปลี่ยน)

---

### Phase 3: Consider Elasticsearch (ถ้า corpus โต)

**When to use:**
- Corpus โตถึง 1,000+ เอกสาร
- ต้องการ advanced features (faceted search, analytics)

**Implementation:**
1. Setup Elasticsearch
2. Index documents
3. Migrate search API

---

### Phase 4: Vector Database (Optional - ถ้าต้องการ Semantic Search)

**When to use:**
- ต้องการ semantic search (หาได้แม้คำไม่ตรง)
- Corpus ใหญ่มาก (10,000+ docs)
- มี budget สำหรับ infrastructure

**Implementation:**
1. Choose Vector DB (pgvector, Pinecone, Qdrant)
2. Generate embeddings (async)
3. Hybrid search (Full-text + Vector)

---

## 📐 Implementation Plan

### Step 1: PostgreSQL Full-Text Search

```sql
-- Migration: Add full-text search indexes
-- File: migrations/add_fulltext_search.sql

-- 1. Enable extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 2. Add search metadata column
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- 3. Create function to update search_vector
CREATE OR REPLACE FUNCTION update_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('thai', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Create trigger
CREATE TRIGGER document_search_vector_update
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_document_search_vector();

-- 5. Create GIN index
CREATE INDEX IF NOT EXISTS idx_documents_search_vector 
ON documents USING gin(search_vector);

-- 6. Create trigram index for fuzzy matching
CREATE INDEX IF NOT EXISTS idx_documents_content_trgm 
ON documents USING gin(content gin_trgm_ops);
```

**Search API:**
```typescript
// Backend API: POST /api/documents/search
async function searchDocuments(query: string, limit: number = 20) {
  const result = await db.query(`
    SELECT 
      id,
      content,
      ts_rank(search_vector, plainto_tsquery('thai', $1)) AS rank,
      ts_headline('thai', content, plainto_tsquery('thai', $1)) AS highlighted
    FROM documents
    WHERE search_vector @@ plainto_tsquery('thai', $1)
    ORDER BY rank DESC
    LIMIT $2
  `, [query, limit]);
  
  return result.rows;
}
```

---

### Step 2: Mapping Service Optimization

```typescript
// Background Job Queue (RabbitMQ)
class DocumentMappingWorker {
  private concurrency = 10; // 10 workers
  
  async processMappingQueue() {
    // Consume from queue
    await rabbitmq.consume('document_mapping_queue', async (message) => {
      const { documentId } = JSON.parse(message.content.toString());
      await this.processMapping(documentId);
    }, { prefetch: this.concurrency });
  }
  
  async processMapping(documentId: string) {
    // Load document and transcription
    const document = await getDocument(documentId);
    const transcription = await getTranscription(document.transcriptionId);
    
    // Word-level mapping
    const mappings = await mapDocumentToChunks(
      document.content,
      transcription.chunks
    );
    
    // Save mappings
    await saveDocumentMappings(documentId, mappings);
  }
}
```

---

## 📊 Performance Benchmarks

### Expected Performance (PostgreSQL FTS)

| Corpus Size | Query Time | Concurrent Queries | Status |
|-------------|-----------|-------------------|--------|
| 50 docs | 5-10ms | 50-100/sec | ✅✅ |
| 300 docs | 20-50ms | 20-50/sec | ✅ |
| 1,000 docs | 50-100ms | 10-20/sec | ✅ |
| 5,000 docs | 100-200ms | 5-10/sec | ⚠️ |
| 10,000+ docs | 200-500ms | 2-5/sec | ❌ (Consider Elasticsearch) |

---

### Expected Performance (Mapping Service)

| Documents | Sequential | Parallel (10) | Background Queue |
|-----------|-----------|---------------|------------------|
| 10 docs | 30s | 3s | 3s (with rate limit) |
| 50 docs | 2.5min | 15s | 15s |
| 100 docs | 5min | 30s | 30s |
| 500 docs | 25min | 2.5min | 2.5min (with rate limit) |

---

## ✅ สรุปและคำแนะนำ

### สำหรับ 200-300 เอกสาร

**✅ ใช้ PostgreSQL Full-Text Search เพียงพอ**

**เหตุผล:**
- Query time: 20-50ms (acceptable)
- Simple setup (no additional infrastructure)
- Cost-effective
- Thai language support

**ไม่แนะนำ Vector Database เพราะ:**
- Overkill สำหรับขนาดนี้
- Latency สูงกว่า (100-200ms)
- Complexity สูง
- Cost เพิ่มขึ้น

---

### สำหรับ 50 เอกสารที่ต้อง Mapping

**✅ ใช้ Parallel Processing + Background Queue**

**เหตุผล:**
- Sequential: 2.5 นาที (ช้าเกินไป)
- Parallel (10 workers): 15 วินาที ✅
- Background queue: ไม่ block user

---

### Future Consideration

**ถ้า corpus โตถึง 1,000+ เอกสาร:**
- Consider Elasticsearch
- Better performance
- Advanced features

**ถ้าต้องการ Semantic Search:**
- Consider Hybrid (Full-text + pgvector)
- หรือ Vector DB (Pinecone/Qdrant)
- แต่ยังไม่จำเป็นสำหรับตอนนี้

---

**Last Updated**: 2024-12-05  
**Status**: Analysis Complete ✅

