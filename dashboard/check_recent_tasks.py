#!/usr/bin/env python3
"""
Check Recent Tasks - ตรวจสอบ 50 tasks ล่าสุดใน server
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

# Add dashboard to path
dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

try:
    from server_constants import SERVERS
except ImportError:
    from config import SERVERS

async def get_tasks(server_name, limit=50):
    """Get tasks from server"""
    server_config = SERVERS[server_name]
    api_url = server_config['api_url']
    
    async with aiohttp.ClientSession() as session:
        url = f'{api_url}/transcribe/'
        async with session.get(url, params={'limit': limit}, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                tasks = await response.json()
                return tasks
            else:
                print(f'Error: {response.status}')
                return []

async def get_task_detail(server_name, task_id):
    """Get detailed task info"""
    server_config = SERVERS[server_name]
    api_url = server_config['api_url']
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f'{api_url}/transcribe/{task_id}'
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
    except:
        pass
    return None

def format_time(time_str):
    """Format time string - assume UTC if no timezone indicator, then convert to UTC+7 (Thai time)"""
    if not time_str:
        return 'N/A'
    try:
        # Parse datetime - handle different formats
        if 'Z' in time_str:
            # Has Z indicator (UTC)
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        elif '+' in time_str or time_str.count('-') > 2:
            # Has timezone offset (e.g., +00:00, +07:00)
            dt = datetime.fromisoformat(time_str)
        else:
            # No timezone info - assume UTC (as per new standard)
            dt = datetime.fromisoformat(time_str.replace('Z', ''))
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Ensure timezone is set (if still naive, assume UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to UTC+7 (Thai time) for display
        thai_tz = timezone(timedelta(hours=7))
        dt_thai = dt.astimezone(thai_tz)
        return dt_thai.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return time_str[:19] if len(time_str) >= 19 else time_str

def format_duration(seconds):
    """Format duration in seconds"""
    if not seconds or seconds <= 0:
        return 'N/A'
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f'{hours}h {minutes}m {secs}s'
    elif minutes > 0:
        return f'{minutes}m {secs}s'
    else:
        return f'{secs}s'

async def main():
    server_name = '4000-ada-sc'
    
    print(f'\n📊 ตรวจสอบ 50 Tasks ล่าสุดใน {server_name}\n')
    print('🔍 กำลังโหลดข้อมูลรายละเอียดของแต่ละ task...\n')
    
    tasks = await get_tasks(server_name, limit=50)
    
    if not tasks:
        print('❌ No tasks found')
        return
    
    # Sort by updated_at or created_at (newest first)
    tasks_sorted = sorted(
        tasks, 
        key=lambda x: x.get('updated_at') or x.get('created_at') or '', 
        reverse=True
    )
    
    print(f'Total tasks found: {len(tasks_sorted)}\n')
    print('='*140)
    header = f"{'No.':<5} {'Task ID':<36} {'Status':<12} {'Created':<20} {'Audio Start':<20} {'End Time':<20} {'Duration':<12} {'Audio Time':<12}"
    print(header)
    print('='*140)
    
    task_times = []
    audio_start_times = []
    
    print('Loading detailed task information...')
    print()
    
    for i, task in enumerate(tasks_sorted[:50], 1):
        task_id = (task.get('task_id') or task.get('id') or 'N/A')[:36]
        status = (task.get('status') or 'unknown').lower()
        
        created_at = task.get('created_at') or task.get('start_time') or ''
        updated_at = task.get('updated_at') or task.get('end_time') or task.get('completed_at') or ''
        
        # Get detailed task info
        task_detail = await get_task_detail(server_name, task_id)
        
        # Try to find actual audio extraction start time
        audio_start_time = None
        audio_extraction_time = None
        transcription_time = None
        
        if task_detail:
            audio_extraction_time = task_detail.get('audio_extraction_time')
            transcription_time = task_detail.get('transcription_time')
            processing_time = task_detail.get('processing_time') or task_detail.get('time_used')
            
            # Calculate audio start time from processing_time
            # Audio extraction start = completed_at - processing_time
            if updated_at and processing_time:
                try:
                    end_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    processing_seconds = float(processing_time)
                    audio_start_dt = end_dt - timedelta(seconds=processing_seconds)
                    audio_start_time = audio_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    audio_start_times.append(audio_start_dt)
                except Exception as e:
                    pass
            
            # Alternative: if audio_extraction_time exists, use it
            elif updated_at and audio_extraction_time:
                try:
                    # Parse updated_at (assume UTC if no timezone)
                    if 'Z' in updated_at:
                        end_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    elif '+' in updated_at:
                        end_dt = datetime.fromisoformat(updated_at)
                    else:
                        end_dt = datetime.fromisoformat(updated_at.replace('Z', ''))
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    
                    # Audio extraction started before transcription
                    if transcription_time:
                        audio_start_dt = end_dt - timedelta(seconds=float(audio_extraction_time) + float(transcription_time))
                    else:
                        audio_start_dt = end_dt - timedelta(seconds=float(audio_extraction_time))
                    audio_start_time = audio_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    audio_start_times.append(audio_start_dt)
                except:
                    pass
        
        start_time = format_time(created_at)
        audio_start_str = audio_start_time or 'N/A'
        end_time = format_time(updated_at)
        
        # Calculate duration from audio start
        duration = 'N/A'
        duration_seconds = None
        
        if audio_start_time and updated_at:
            try:
                # Parse times (assume UTC if no timezone)
                if 'Z' in audio_start_time:
                    start = datetime.fromisoformat(audio_start_time.replace('Z', '+00:00'))
                elif '+' in audio_start_time:
                    start = datetime.fromisoformat(audio_start_time)
                else:
                    start = datetime.fromisoformat(audio_start_time.replace('Z', ''))
                    start = start.replace(tzinfo=timezone.utc)
                
                if 'Z' in updated_at:
                    end = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                elif '+' in updated_at:
                    end = datetime.fromisoformat(updated_at)
                else:
                    end = datetime.fromisoformat(updated_at.replace('Z', ''))
                    end = end.replace(tzinfo=timezone.utc)
                
                diff = (end - start).total_seconds()
                if diff > 0:
                    duration_seconds = diff
                    duration = format_duration(diff)
            except:
                pass
        
        if duration == 'N/A' and task_detail and task_detail.get('processing_time'):
            pt = float(task_detail.get('processing_time', 0))
            if pt > 0:
                duration_seconds = pt
                duration = format_duration(pt)
        
        # Show processing time breakdown if available
        audio_time_str = ''
        if task_detail:
            if audio_extraction_time:
                audio_time_str = f'Extract: {format_duration(float(audio_extraction_time))}'
            elif transcription_time:
                trans_time = float(transcription_time)
                proc_time = float(task_detail.get('processing_time') or task_detail.get('time_used') or 0)
                if proc_time > trans_time:
                    audio_time_str = f'Trans: {format_duration(trans_time)}'
        
        print(f'{i:<5} {task_id:<36} {status:<12} {start_time:<20} {audio_start_str:<20} {end_time:<20} {duration:<12} {audio_time_str:<12}')
        
        if audio_start_time:
            task_times.append({
                'task_id': task_id,
                'audio_start': audio_start_time,
                'end': updated_at,
                'status': status
            })
    
    # Summary
    print('\n' + '='*140)
    print('📈 Summary:')
    print('='*140)
    
    if audio_start_times:
        earliest_audio_start = min(audio_start_times)
        # Convert to UTC+7 for display
        if earliest_audio_start.tzinfo is None:
            earliest_audio_start = earliest_audio_start.replace(tzinfo=timezone.utc)
        thai_tz = timezone(timedelta(hours=7))
        earliest_thai = earliest_audio_start.astimezone(thai_tz)
        print(f'✅ First Audio Extraction Start: {earliest_thai.strftime("%Y-%m-%d %H:%M:%S")} (UTC+7)')
    
    if task_times:
        # Find latest end
        latest_end = None
        for task_time in task_times:
            if task_time['end']:
                try:
                    # Parse end time (assume UTC if no timezone)
                    end_str = task_time['end']
                    if 'Z' in end_str:
                        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    elif '+' in end_str:
                        end_dt = datetime.fromisoformat(end_str)
                    else:
                        end_dt = datetime.fromisoformat(end_str.replace('Z', ''))
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    
                    if latest_end is None or end_dt > latest_end:
                        latest_end = end_dt
                except:
                    pass
        
        if latest_end:
            # Convert to UTC+7 for display
            if latest_end.tzinfo is None:
                latest_end = latest_end.replace(tzinfo=timezone.utc)
            thai_tz = timezone(timedelta(hours=7))
            latest_thai = latest_end.astimezone(thai_tz)
            print(f'✅ Last Task End: {latest_thai.strftime("%Y-%m-%d %H:%M:%S")} (UTC+7)')
        
        if audio_start_times and latest_end:
            earliest_audio_start = min(audio_start_times)
            total_diff = (latest_end - earliest_audio_start).total_seconds()
            print(f'⏱️  Total Duration (Audio Start to Last End): {format_duration(total_diff)} ({total_diff:.0f} seconds)')
    
    # Also show created_at summary for comparison
    if tasks_sorted:
        created_times = []
        for task in tasks_sorted[:50]:
            created_at = task.get('created_at') or ''
            if created_at:
                try:
                    # Parse created_at (assume UTC if no timezone)
                    if 'Z' in created_at:
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    elif '+' in created_at:
                        created_dt = datetime.fromisoformat(created_at)
                    else:
                        created_dt = datetime.fromisoformat(created_at.replace('Z', ''))
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    created_times.append(created_dt)
                except:
                    pass
        
        if created_times:
            earliest_created = min(created_times)
            # Convert to UTC+7 for display
            if earliest_created.tzinfo is None:
                earliest_created = earliest_created.replace(tzinfo=timezone.utc)
            thai_tz = timezone(timedelta(hours=7))
            earliest_thai = earliest_created.astimezone(thai_tz)
            print(f'\n📝 First Task Created (Queue): {earliest_thai.strftime("%Y-%m-%d %H:%M:%S")} (UTC+7)')
            print(f'   ⚠️  Note: This is when task was queued, not when processing started')
        
        # Status breakdown
        status_counts = {}
        for task in tasks_sorted[:50]:
            status = (task.get('status') or 'unknown').lower()
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f'\n📊 Status Breakdown:')
        for status, count in sorted(status_counts.items()):
            print(f'   {status}: {count}')
    
    print('\n' + '='*140)

if __name__ == '__main__':
    asyncio.run(main())

