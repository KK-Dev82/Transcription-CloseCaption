"""
Lua scripts สำหรับ atomic operations ใน Redis
ใช้เพื่อป้องกัน race conditions ใน windowed/JIT enqueue
"""

# Lua script: Atomic claim next chunk index
# Returns: [claimed_index, inflight_after] หรือ [nil, nil] ถ้าไม่สามารถ claim ได้
# ใช้ SETNX เพื่อป้องกัน enqueue chunk ซ้ำ (atomic guard)
CLAIM_NEXT_CHUNK_INDEX_SCRIPT = """
local chunks_metadata_key = KEYS[1]
local inflight_key = KEYS[2]
local enqueued_guard_key = KEYS[3]
local inflight_limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

-- อ่าน chunks_metadata
local chunks_metadata_str = redis.call('GET', chunks_metadata_key)
if not chunks_metadata_str then
    return {nil, nil}
end

local chunks_metadata = cjson.decode(chunks_metadata_str)
local next_chunk_index = chunks_metadata['next_chunk_index'] or 0
local total_chunks = chunks_metadata['total_chunks'] or 0

-- ตรวจสอบว่ายังมี chunks เหลือ
if next_chunk_index >= total_chunks then
    return {nil, nil}
end

-- อ่าน inflight count
local inflight_count = tonumber(redis.call('GET', inflight_key) or '0')

-- ตรวจสอบ inflight limit
if inflight_count >= inflight_limit then
    return {nil, nil}
end

-- ตรวจสอบว่า chunk index นี้ถูก enqueue แล้วหรือยัง (atomic guard ด้วย SETNX)
local guard_key = string.format('%s:%d', enqueued_guard_key, next_chunk_index)
local guard_set = redis.call('SETNX', guard_key, '1')
if guard_set == 0 then
    -- Chunk นี้ถูก enqueue แล้ว (อาจเกิดจาก race condition)
    return {nil, nil}
end

-- ตั้ง TTL สำหรับ guard key
redis.call('EXPIRE', guard_key, ttl)

-- Claim chunk index นี้: update next_chunk_index + increment inflight
chunks_metadata['next_chunk_index'] = next_chunk_index + 1
redis.call('SETEX', chunks_metadata_key, ttl, cjson.encode(chunks_metadata))

-- Increment inflight counter
local new_inflight = redis.call('INCR', inflight_key)
redis.call('EXPIRE', inflight_key, ttl)

return {next_chunk_index, new_inflight}
"""

# Lua script: Decrement inflight counter เมื่อ chunk เสร็จ
DECR_INFLIGHT_SCRIPT = """
local inflight_key = KEYS[1]
local guard_key = KEYS[2]
local ttl = tonumber(ARGV[1])

-- Decrement inflight counter
local new_inflight = redis.call('DECR', inflight_key)
redis.call('EXPIRE', inflight_key, ttl)

-- ลบ guard (optional, แต่จะช่วยลบ key ที่ไม่จำเป็น)
-- redis.call('DEL', guard_key)

return new_inflight
"""