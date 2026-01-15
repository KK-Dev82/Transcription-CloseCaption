# Performance Records & Configuration Optimization Guide

Generated: 2026-01-12T19:32:19.975798

## Performance Records Summary

### Overall Statistics
- Total Jobs Analyzed: 51
- Average Time per Job: 8.33 minutes
- Average Throughput: 2.04 jobs/minute
- Best Throughput: 2.56 jobs/minute
- Time Range: 7.81 - 9.20 minutes

### Test Batches

#### Batch 1
- Jobs: 20
- Average time per job: 9.20 minutes
- Throughput: 2.17 jobs/minute
- Preprocess: 17.2s (3.1%)
- Wait chunks: 162.3s (29.4%)
- Fetch + Merge: 11.4s (2.1%)

#### Batch 2
- Jobs: 20
- Average time per job: 7.81 minutes
- Throughput: 2.56 jobs/minute
- Preprocess: 18.8s (4.0%)
- Wait chunks: 134.0s (28.6%)
- Fetch + Merge: 10.1s (2.1%)

#### Batch 3
- Jobs: 11
- Average time per job: 7.97 minutes
- Throughput: 1.38 jobs/minute
- Preprocess: 14.3s (3.0%)
- Wait chunks: 245.6s (51.4%)
- Fetch + Merge: 12.5s (2.6%)

## Current Configuration

- CHUNK_ENQUEUE_WINDOW_SIZE: 2
- CHUNK_INFLIGHT_LIMIT_PER_JOB: 4
- GPU_WORKERS_PER_GPU: 8
- MAX_PREPROCESS_QUEUE_SIZE: 25
- NUM_CPU_WORKERS: 6
- NUM_GPUS: 2
- NUM_PREPROCESS_WORKERS: 6

## Optimization Recommendations


### GPU_WORKERS_PER_GPU (Priority: HIGH)
- **Current**: 8
- **Recommended**: 10
- **Impact**: HIGH - Will increase GPU utilization from 0-29% to 50-70%
- **Risk**: LOW - VRAM has 90% headroom
- **Reason**: GPU utilization is very low, VRAM has plenty of headroom

### CHUNK_INFLIGHT_LIMIT_PER_JOB (Priority: HIGH)
- **Current**: 4
- **Recommended**: 6
- **Impact**: HIGH - Will reduce wait_chunks time (currently 29-38% of total)
- **Risk**: LOW - Will increase throughput per job
- **Reason**: Wait chunks is the main bottleneck (33.6% of total time)

### CHUNK_ENQUEUE_WINDOW_SIZE (Priority: MEDIUM)
- **Current**: 2
- **Recommended**: 8
- **Impact**: MEDIUM - Will keep GPU fed with work continuously
- **Risk**: LOW - Will improve fairness and reduce gaps
- **Reason**: Current window (2) is small, can increase to keep GPU busy

### NUM_PREPROCESS_WORKERS (Priority: MEDIUM)
- **Current**: 6
- **Recommended**: 8
- **Impact**: MEDIUM - Will reduce preprocessing time (currently 3.4% of total)
- **Risk**: LOW - CPU usage is low (~10%)
- **Reason**: CPU usage is low, can handle more preprocess workers

### NUM_CPU_WORKERS (Priority: MEDIUM)
- **Current**: 6
- **Recommended**: 8
- **Impact**: MEDIUM - Will reduce aggregator processing time
- **Risk**: LOW - CPU usage is low
- **Reason**: CPU queue has backlog, aggregator is bottleneck

## Expected Improvements

- Current Throughput: 2.04 jobs/minute
- Expected Improvement: 20-30% increase
- Expected New Throughput: ~2.55 jobs/minute
- For 25 jobs: ~0.2 minutes (estimated)

## Implementation Steps

1. Update `.env.runpod` with recommended values
2. Restart workers: `./scripts/pod/restart-rq-workers.sh`
3. Test with 10-15 jobs first to verify
4. Monitor GPU utilization and VRAM usage
5. Adjust if needed based on results
