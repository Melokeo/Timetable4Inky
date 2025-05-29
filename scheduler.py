#!/usr/bin/env python3
import time
import threading
from datetime import datetime, timedelta, date
from enum import Enum
import os
import sys
import heapq
import signal

# local modules
from draw import TotalRenderer, get_timeline_panel_ranges
from routines import rt_workday, routines
from task import find_current_task, Task
from uploader import TimelineUploader
from display import display
from alarm import bark

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
daemon = None

class UpdateTrigger(Enum):
    TASK_END = "task_end"
    TASK_START = "task_start" 
    PANEL_SHIFT = "panel_shift"
    PERIODIC = "periodic"

class ScheduleDaemon:
    def __init__(self, routine):
        self.routine = routine
        self.last_update = datetime.now()
        self.current_task = None
        self.current_panels = None
        self.running = False
        self.min_interval = timedelta(minutes=3)
        self.periodic_interval = timedelta(minutes=30)
        self.renderer = TotalRenderer()
        self.uploader = TimelineUploader(os.path.join(BASE_DIR, 'cfg', 'upload_config.json'))
        self.update_timer = None
        self.update_queue = []  # Priority queue of (datetime, trigger) tuples
        self.stop_event = threading.Event()
        self.stat_str = ''
        
    def start(self):
        self.running = True
        print("Schedule daemon started")
        
        # Schedule all updates for today
        self._schedule_today_updates()
        
        # Start the update loop
        self._schedule_next_update()
        
        # Initial update
        self._update_display()
        self.uploader.upload_png(note=self.stat_str)
        
        # Block until stop is called
        while self.running:
            self.stop_event.wait(timeout=1) #TODO bit stupid
            if self.stop_event.is_set():
                break
                    
    def _schedule_today_updates(self):
        """Pre-calculate all update times for today"""
        now = datetime.now()
        today_tasks = self.routine.create_schedule(date.today())
        
        # Clear existing queue
        self.update_queue = []
        
        # Add task start/end times
        for task in today_tasks:
            if task.start_time > now:
                heapq.heappush(self.update_queue, (task.start_time, UpdateTrigger.TASK_START))
            
            task_end = task.start_time + task.duration
            if task_end > now:
                heapq.heappush(self.update_queue, (task_end, UpdateTrigger.TASK_END))
        
        # Add panel shift times (for now 12:00)
        panel_time = now.replace(hour=12, minute=0, second=0, microsecond=1)
        if panel_time > now:
            heapq.heappush(self.update_queue, (panel_time, UpdateTrigger.PANEL_SHIFT))
        
        # Add periodic updates (every 30 mins from last update)
        next_periodic = self.last_update + self.periodic_interval
        while next_periodic < now.replace(hour=23, minute=59):
            if next_periodic > now:
                heapq.heappush(self.update_queue, (next_periodic, UpdateTrigger.PERIODIC))
            next_periodic += self.periodic_interval
    
    def _schedule_next_update(self):
        """Schedule the next update based on the queue"""
        if not self.running:
            return
            
        now = datetime.now()
        
        # Find next valid update time (respecting min_interval)
        next_update = None
        next_trigger = None
        
        while self.update_queue:
            update_time, trigger = heapq.heappop(self.update_queue)
            
            # Skip past updates
            if update_time <= now:
                continue
                
            # Check if respects minimum interval
            if update_time >= self.last_update + self.min_interval:
                next_update = update_time
                next_trigger = trigger
                break
        
        if next_update:
            # Calculate delay in seconds
            delay = (next_update - now).total_seconds()

            self.stat_str = f"Next update scheduled: {next_update.strftime('%H:%M:%S')} ({next_trigger.value})"
            print(self.stat_str)
            
            # Cancel existing timer if any
            if self.update_timer:
                self.update_timer.cancel()
            
            # Schedule the update
            self.update_timer = threading.Timer(delay, self._perform_update, args=[next_trigger])
            self.update_timer.start()
        else:
            # No more updates today, schedule for tomorrow morning
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
            delay = (tomorrow - now).total_seconds()
            
            self.stat_str = f"No more updates today. Scheduling for tomorrow at {tomorrow.strftime('%H:%M:%S')}"
            print(self.stat_str)
            
            if self.update_timer:
                self.update_timer.cancel()
                
            self.update_timer = threading.Timer(delay, self._start_new_day)
            self.update_timer.start()
    
    def _perform_update(self, trigger):
        """Perform the scheduled update"""
        if not self.running:
            return
            
        print(f"Update triggered: {trigger.value}")
        
        # alarm
        if trigger == UpdateTrigger.TASK_START:
            now = datetime.now()
            today_tasks = self.routine.create_schedule(date.today())        #TODO This is not clean.
            curr_task:Task = find_current_task(today_tasks, now)
            if curr_task and curr_task.has_alarm:
                print(f'Playing alarm {curr_task.alarm_sound} for {curr_task.title}')
                bark(curr_task.alarm_sound)

        # update display
        self._update_display()
        self.last_update = datetime.now()

        # schedule next
        self._schedule_next_update()
        
        try:
            self.uploader.upload_png(note=self.stat_str)
        except Exception as e:
            print(f"Upload error: {e}")
    
    def _start_new_day(self):
        """Reset for a new day"""
        if not self.running:
            return
            
        print("Starting new day...")
        self._schedule_today_updates()
        self._perform_update(UpdateTrigger.TASK_START)
        
    def _update_display(self):
        """Update display and save preview"""
        img = self.renderer.create_schedule_image(self.routine)
        display.set_image(img)

        out_path = os.path.join(BASE_DIR, 'output')
        if not os.path.exists(out_path): os.mkdir(out_path)
        img.save(os.path.join(out_path, 'schedule_preview.png'))
        
        # Update current task/panels tracking
        now = datetime.now()
        today_tasks = self.routine.create_schedule(date.today())
        self.current_task = find_current_task(today_tasks, now)
        self.current_panels = get_timeline_panel_ranges(now)
        
        print(f"Preview saved at {now.strftime('%H:%M:%S')}")
                
    def stop(self):
        self.running = False
        if self.update_timer:
            self.update_timer.cancel()
        self.stop_event.set()
        print("Daemon stopped")

def signal_handler(signum, frame):
    global daemon
    if daemon:
        daemon.stop()
    sys.exit(0)

if __name__ == "__main__":
    if (d:=datetime.now().strftime('%m%d')) in routines.keys():
        daemon = ScheduleDaemon(routines[d])
    else:
        daemon = ScheduleDaemon(rt_workday)
    signal.signal(signal.SIGINT, signal_handler)
    daemon.start()