#!/usr/bin/env python3
"""
Monitor Test Jobs - ติดตาม Logs สำหรับ Dashboard จนกว่า Transcription จะสำเร็จ
สำหรับวิเคราะห์ผลลัพธ์และปรับปรุงต่อไป

Usage:
    python monitor_test_jobs.py --server 4000-ada-sc --task-ids task1,task2,task3
    python monitor_test_jobs.py --server 4000-ada-sc --batch-id batch-123
    python monitor_test_jobs.py --server 4000-ada-sc --count 50  # Monitor latest 50 tasks
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import aiohttp

# Import server config
try:
    from server_constants import SERVERS
except ImportError:
    import sys
    from pathlib import Path
    dashboard_dir = Path(__file__).parent
    if str(dashboard_dir) not in sys.path:
        sys.path.insert(0, str(dashboard_dir))
    from server_constants import SERVERS

# Configuration
DASHBOARD_URL = "http://localhost:8020"
CHECK_INTERVAL = 10  # seconds
MAX_WAIT_TIME = 3600  # 1 hour max wait time
OUTPUT_DIR = Path(__file__).parent / "monitoring_results"

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}")

def print_status(text, color=Colors.BLUE):
    """Print status message"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.CYAN}[{timestamp}]{Colors.RESET} {color}{text}{Colors.RESET}")

def print_success(text):
    """Print success message"""
    print_status(f"✅ {text}", Colors.GREEN)

def print_warning(text):
    """Print warning message"""
    print_status(f"⚠️  {text}", Colors.YELLOW)

def print_error(text):
    """Print error message"""
    print_status(f"❌ {text}", Colors.RED)

class TestJobMonitor:
    """Monitor test jobs until completion"""
    
    def __init__(self, server_name: str, dashboard_url: str = DASHBOARD_URL):
        self.server_name = server_name
        self.dashboard_url = dashboard_url.rstrip('/')
        
        if server_name not in SERVERS:
            raise ValueError(f"Server '{server_name}' not found in configuration")
        
        self.server_config = SERVERS[server_name]
        self.api_url = self.server_config["api_url"]
        self.task_ids: List[str] = []
        self.task_data: Dict[str, Dict] = {}
        self.start_time = datetime.now()
        
    async def get_tasks_from_dashboard(self, limit: int = 100) -> List[Dict]:
        """Get tasks from dashboard API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.dashboard_url}/api/server/{self.server_name}/tasks"
                params = {"limit": limit}
                
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("tasks", [])
                    else:
                        error_text = await response.text()
                        print_error(f"Dashboard API returned {response.status}: {error_text[:200]}")
                        return []
        except Exception as e:
            print_error(f"Error getting tasks from dashboard: {e}")
            return []
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status from remote server"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/transcribe/{task_id}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print_warning(f"Error getting status for task {task_id[:16]}...: {e}")
            return None
    
    async def get_batch_tasks(self, batch_id: str) -> List[str]:
        """Get task IDs from batch"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.dashboard_url}/api/batch/{batch_id}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("task_ids", [])
                    else:
                        print_error(f"Batch {batch_id} not found")
                        return []
        except Exception as e:
            print_error(f"Error getting batch tasks: {e}")
            return []
    
    def set_task_ids(self, task_ids: List[str]):
        """Set task IDs to monitor"""
        self.task_ids = task_ids
        print_success(f"Monitoring {len(task_ids)} tasks")
    
    async def update_task_statuses(self):
        """Update status of all tasks"""
        tasks = await asyncio.gather(
            *[self.get_task_status(task_id) for task_id in self.task_ids],
            return_exceptions=True
        )
        
        for task_id, task_data in zip(self.task_ids, tasks):
            if isinstance(task_data, Exception):
                print_warning(f"Error getting status for {task_id[:16]}...: {task_data}")
                continue
            
            if task_data:
                self.task_data[task_id] = task_data
            elif task_id not in self.task_data:
                # Task not found yet, keep checking
                self.task_data[task_id] = {"status": "unknown", "task_id": task_id}
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of task statuses"""
        summary = {
            "completed": 0,
            "failed": 0,
            "processing": 0,
            "pending": 0,
            "stopped": 0,
            "unknown": 0
        }
        
        for task_id in self.task_ids:
            task = self.task_data.get(task_id, {})
            status = task.get("status", "unknown").lower()
            summary[status] = summary.get(status, 0) + 1
        
        return summary
    
    def all_tasks_finished(self) -> bool:
        """Check if all tasks are finished"""
        summary = self.get_status_summary()
        active_statuses = ["processing", "pending", "unknown"]
        return sum(summary.get(status, 0) for status in active_statuses) == 0
    
    def print_status(self):
        """Print current status"""
        summary = self.get_status_summary()
        total = len(self.task_ids)
        completed = summary.get("completed", 0)
        failed = summary.get("failed", 0)
        processing = summary.get("processing", 0)
        pending = summary.get("pending", 0)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        
        print_status(
            f"Progress: {completed + failed}/{total} finished "
            f"(✅ {completed} completed, ❌ {failed} failed, "
            f"⏳ {processing} processing, 📋 {pending} pending) "
            f"| Elapsed: {elapsed_str}"
        )
    
    async def monitor_until_complete(self, check_interval: int = CHECK_INTERVAL):
        """Monitor tasks until all are complete"""
        print_header(f"Monitoring {len(self.task_ids)} tasks on {self.server_name}")
        print_status(f"Dashboard: {self.dashboard_url}")
        print_status(f"Server API: {self.api_url}")
        print_status(f"Check interval: {check_interval} seconds")
        print_status(f"Max wait time: {MAX_WAIT_TIME} seconds")
        print()
        
        iteration = 0
        last_summary = {}
        
        while True:
            iteration += 1
            await self.update_task_statuses()
            
            # Print status if changed
            current_summary = self.get_status_summary()
            if current_summary != last_summary:
                self.print_status()
                last_summary = current_summary.copy()
            
            # Check if all finished
            if self.all_tasks_finished():
                print_success("All tasks completed!")
                break
            
            # Check timeout
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed > MAX_WAIT_TIME:
                print_warning(f"Timeout reached ({MAX_WAIT_TIME}s). Stopping monitoring.")
                break
            
            # Wait before next check
            await asyncio.sleep(check_interval)
        
        return self.task_data
    
    def analyze_results(self) -> Dict:
        """Analyze transcription results"""
        analysis = {
            "total_tasks": len(self.task_ids),
            "completed": 0,
            "failed": 0,
            "processing_times": [],
            "audio_extraction_times": [],
            "transcription_times": [],
            "total_durations": [],
            "text_lengths": [],
            "chunk_counts": [],
            "thai_text_quality": {
                "has_thai": 0,
                "total_chars": 0,
                "thai_chars": 0
            },
            "errors": []
        }
        
        for task_id, task in self.task_data.items():
            status = task.get("status", "unknown").lower()
            
            if status == "completed":
                analysis["completed"] += 1
                
                # Processing times
                audio_time = task.get("audio_extraction_time")
                transcribe_time = task.get("transcription_time")
                processing_time = task.get("processing_time") or task.get("time_used")
                
                if audio_time is not None:
                    analysis["audio_extraction_times"].append(float(audio_time))
                if transcribe_time is not None:
                    analysis["transcription_times"].append(float(transcribe_time))
                if processing_time is not None:
                    analysis["processing_times"].append(float(processing_time))
                
                # Video duration
                duration = task.get("total_duration") or task.get("video_duration") or task.get("duration")
                if duration:
                    analysis["total_durations"].append(float(duration))
                
                # Text analysis
                full_text = task.get("full_text") or task.get("corrected_text") or task.get("original_text")
                if not full_text and task.get("chunks"):
                    chunk_texts = [chunk.get("text", "") for chunk in task.get("chunks", []) if chunk.get("text")]
                    full_text = " ".join(chunk_texts).strip()
                
                if full_text:
                    text_len = len(full_text)
                    analysis["text_lengths"].append(text_len)
                    
                    # Thai text detection
                    thai_chars = sum(1 for c in full_text if '\u0e00' <= c <= '\u0e7f')
                    if thai_chars > 0:
                        analysis["thai_text_quality"]["has_thai"] += 1
                        analysis["thai_text_quality"]["total_chars"] += text_len
                        analysis["thai_text_quality"]["thai_chars"] += thai_chars
                
                # Chunk count
                chunks = task.get("chunks", [])
                if chunks:
                    analysis["chunk_counts"].append(len(chunks))
            
            elif status == "failed":
                analysis["failed"] += 1
                error_msg = task.get("error") or task.get("error_message") or "Unknown error"
                analysis["errors"].append({
                    "task_id": task_id[:16] + "...",
                    "error": error_msg[:200]
                })
        
        return analysis
    
    def generate_report(self, analysis: Dict) -> str:
        """Generate analysis report"""
        report = []
        report.append("\n" + "="*80)
        report.append("📊 TRANSCRIPTION TEST RESULTS ANALYSIS")
        report.append("="*80)
        report.append(f"\nServer: {self.server_name}")
        report.append(f"Total Tasks: {analysis['total_tasks']}")
        report.append(f"✅ Completed: {analysis['completed']}")
        report.append(f"❌ Failed: {analysis['failed']}")
        report.append(f"Success Rate: {(analysis['completed'] / analysis['total_tasks'] * 100):.1f}%")
        
        # Processing times
        if analysis["processing_times"]:
            times = analysis["processing_times"]
            report.append(f"\n⏱️  Processing Times:")
            report.append(f"   Average: {sum(times) / len(times):.2f}s")
            report.append(f"   Min: {min(times):.2f}s")
            report.append(f"   Max: {max(times):.2f}s")
        
        if analysis["audio_extraction_times"]:
            times = analysis["audio_extraction_times"]
            report.append(f"\n🎵 Audio Extraction Times:")
            report.append(f"   Average: {sum(times) / len(times):.2f}s")
            report.append(f"   Min: {min(times):.2f}s")
            report.append(f"   Max: {max(times):.2f}s")
        
        if analysis["transcription_times"]:
            times = analysis["transcription_times"]
            report.append(f"\n🎤 Transcription Times:")
            report.append(f"   Average: {sum(times) / len(times):.2f}s")
            report.append(f"   Min: {min(times):.2f}s")
            report.append(f"   Max: {max(times):.2f}s")
        
        # Video durations
        if analysis["total_durations"]:
            durations = analysis["total_durations"]
            total_duration = sum(durations)
            report.append(f"\n📹 Video Durations:")
            report.append(f"   Total: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
            report.append(f"   Average: {total_duration / len(durations):.1f}s per video")
        
        # Text quality
        if analysis["text_lengths"]:
            lengths = analysis["text_lengths"]
            report.append(f"\n📝 Text Analysis:")
            report.append(f"   Average length: {sum(lengths) / len(lengths):.0f} characters")
            report.append(f"   Min: {min(lengths)} characters")
            report.append(f"   Max: {max(lengths)} characters")
        
        # Thai text quality
        thai_quality = analysis["thai_text_quality"]
        if thai_quality["has_thai"] > 0:
            thai_ratio = thai_quality["thai_chars"] / thai_quality["total_chars"] * 100 if thai_quality["total_chars"] > 0 else 0
            report.append(f"\n🇹🇭 Thai Text Quality:")
            report.append(f"   Tasks with Thai text: {thai_quality['has_thai']}/{analysis['completed']}")
            report.append(f"   Thai character ratio: {thai_ratio:.1f}%")
            report.append(f"   Total Thai characters: {thai_quality['thai_chars']:,}")
        else:
            report.append(f"\n🇹🇭 Thai Text Quality:")
            report.append(f"   ⚠️  No Thai text detected in completed tasks")
        
        # Chunks
        if analysis["chunk_counts"]:
            chunks = analysis["chunk_counts"]
            report.append(f"\n📑 Chunks:")
            report.append(f"   Average: {sum(chunks) / len(chunks):.1f} chunks per task")
            report.append(f"   Min: {min(chunks)} chunks")
            report.append(f"   Max: {max(chunks)} chunks")
        
        # Errors
        if analysis["errors"]:
            report.append(f"\n❌ Errors ({len(analysis['errors'])}):")
            for error in analysis["errors"][:10]:  # Show first 10
                report.append(f"   - {error['task_id']}: {error['error']}")
            if len(analysis["errors"]) > 10:
                report.append(f"   ... and {len(analysis['errors']) - 10} more errors")
        
        report.append("\n" + "="*80)
        return "\n".join(report)
    
    def save_results(self, analysis: Dict):
        """Save results to file"""
        OUTPUT_DIR.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"test_results_{self.server_name}_{timestamp}.json"
        filepath = OUTPUT_DIR / filename
        
        results = {
            "server_name": self.server_name,
            "timestamp": timestamp,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "task_ids": self.task_ids,
            "task_data": self.task_data,
            "analysis": analysis
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print_success(f"Results saved to: {filepath}")
        return filepath

async def main():
    parser = argparse.ArgumentParser(description="Monitor test jobs until completion")
    parser.add_argument("--server", required=True, help="Server name (e.g., 4000-ada-sc)")
    parser.add_argument("--task-ids", help="Comma-separated task IDs")
    parser.add_argument("--batch-id", help="Batch ID to monitor")
    parser.add_argument("--count", type=int, help="Monitor latest N tasks")
    parser.add_argument("--dashboard-url", default=DASHBOARD_URL, help="Dashboard URL")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="Check interval in seconds")
    
    args = parser.parse_args()
    
    try:
        monitor = TestJobMonitor(args.server, args.dashboard_url)
        
        # Get task IDs
        if args.task_ids:
            task_ids = [tid.strip() for tid in args.task_ids.split(',')]
            monitor.set_task_ids(task_ids)
        elif args.batch_id:
            print_status(f"Getting tasks from batch {args.batch_id}...")
            task_ids = await monitor.get_batch_tasks(args.batch_id)
            if task_ids:
                monitor.set_task_ids(task_ids)
            else:
                print_error("No tasks found in batch")
                return 1
        elif args.count:
            print_status(f"Getting latest {args.count} tasks...")
            tasks = await monitor.get_tasks_from_dashboard(limit=args.count)
            if tasks:
                task_ids = [task.get("task_id") or task.get("id") for task in tasks if task.get("task_id") or task.get("id")]
                monitor.set_task_ids(task_ids)
            else:
                print_error("No tasks found")
                return 1
        else:
            print_error("Must specify --task-ids, --batch-id, or --count")
            return 1
        
        if not monitor.task_ids:
            print_error("No tasks to monitor")
            return 1
        
        # Monitor until complete
        await monitor.monitor_until_complete(check_interval=args.interval)
        
        # Analyze results
        print_header("Analyzing Results")
        analysis = monitor.analyze_results()
        
        # Generate and print report
        report = monitor.generate_report(analysis)
        print(report)
        
        # Save results
        filepath = monitor.save_results(analysis)
        
        print_success(f"\n✅ Monitoring complete! Results saved to: {filepath}")
        return 0
        
    except KeyboardInterrupt:
        print_warning("\nMonitoring interrupted by user")
        return 1
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

