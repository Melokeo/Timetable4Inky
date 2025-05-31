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
    def __init__(self):
        self.routine = None
        self.last_update = datetime.now()
        self.current_task = None
        self.current_panels = None
        self.running = False
        self.min_interval = timedelta(minutes=3)
        self.periodic_interval = timedelta(minutes=30)
        self.renderer = TotalRenderer()
        self.uploader = TimelineUploader(os.path.join(BASE_DIR, 'cfg', 'upload_config.json'))
        self.update_timer = None
        self.update_queue = []  # queue of (datetime, trigger)
        self.stop_event = threading.Event()
        self.stat_str = ''
        self.silent_start_hour = 1
        self.silent_end_hour = 6
        
    def start(self):
        self.running = True
        self.routine = self._get_today_routine()
        print("Schedule daemon started")
        
        self._schedule_today_updates()
        self._schedule_next_update()
        
        # Initial update
        self._update_display()
        self.uploader.upload_png(note=self.stat_str)
        
        # allow keybd interrupt
        while self.running:
            self.stop_event.wait(timeout=1) #TODO bit stupid
            if self.stop_event.is_set():
                break
                    
    def _schedule_today_updates(self):
        """Pre-calculate all update times for today"""
        now = datetime.now()
        today_tasks = self.routine.create_schedule(date.today())
        
        self.update_queue = []
        
        # add task start/end
        for task in today_tasks:
            if task.start_time > now:
                heapq.heappush(self.update_queue, (task.start_time, UpdateTrigger.TASK_START))
            
            task_end = task.start_time + task.duration
            if task_end > now:
                heapq.heappush(self.update_queue, (task_end, UpdateTrigger.TASK_END))
        
        # add panel shift 
        panel_time = now.replace(hour=12, minute=0, second=0, microsecond=1)
        if panel_time > now:
            heapq.heappush(self.update_queue, (panel_time, UpdateTrigger.PANEL_SHIFT))
        
        # fill task gaps
        self._schedule_fill_periodic(today_tasks, now)

    def _schedule_fill_periodic(self, tasks, now):
        """Fill gaps between task events with periodic updates"""
        # Get all future task events, sorted
        events = []
        for task in tasks:
            if task.start_time > now:
                events.append(task.start_time)
            task_end = task.start_time + task.duration  
            if task_end > now:
                events.append(task_end)
        
        events.sort()
        end_day = now.replace(hour=23, minute=59)
        
        if not events:
            # No events: fill every periodic_interval until end of day
            t = now + self.periodic_interval
            while t < end_day:
                heapq.heappush(self.update_queue, (t, UpdateTrigger.PERIODIC))
                t += self.periodic_interval
            return
        
        # fill from now→first event
        t = now + self.periodic_interval
        while t < events[0]:
            heapq.heappush(self.update_queue, (t, UpdateTrigger.PERIODIC))
            t += self.periodic_interval
        
        # fill b/w each pair of events
        for i in range(len(events) - 1):
            start, end = events[i] + self.periodic_interval, events[i+1]
            t = start
            while t < end:
                heapq.heappush(self.update_queue, (t, UpdateTrigger.PERIODIC))
                t += self.periodic_interval
        
        # fill after last event → end of day
        t = events[-1] + self.periodic_interval
        while t < end_day:
            heapq.heappush(self.update_queue, (t, UpdateTrigger.PERIODIC))
            t += self.periodic_interval
    
        # print(list(self.update_queue))

    def _schedule_next_update(self):
        if not self.running:
            return
        now = datetime.now()
        earliest_allowed = self.last_update + self.min_interval
    
        eligible_updates = []
        temp_queue = []
        while self.update_queue:
            update_time, trigger = heapq.heappop(self.update_queue)
            if update_time <= now:
                continue
                
            if update_time >= earliest_allowed:
                eligible_updates.append((update_time, trigger))
            else:
                # Reschedule to earliest allowed time
                temp_queue.append((earliest_allowed, trigger))
        
        # Put back any rescheduled items
        for item in temp_queue:
            heapq.heappush(self.update_queue, item)
        
        if eligible_updates:
            # closet update
            eligible_updates.sort(key=lambda x: (x[0], not self._is_task_trigger(x[1])))
            next_update, next_trigger = eligible_updates[0]
            
            # Put back non-selected updates
            for update in eligible_updates[1:]:
                heapq.heappush(self.update_queue, update)
        else:
            # No eligible updates, try queue again
            if self.update_queue:
                next_update, next_trigger = heapq.heappop(self.update_queue)
            else:
                next_update = next_trigger = None
        
        if next_update:
            delay = (next_update - now).total_seconds()
            decoupled = " [decoupled]" if self._in_silent_hour() else ''
            self.stat_str = f"Next update scheduled: {next_update.strftime('%H:%M:%S')} ({next_trigger.value}){decoupled}"
            print(self.stat_str)
            
            if self.update_timer:
                self.update_timer.cancel()
            
            self.update_timer = threading.Timer(delay, self._perform_update, args=[next_trigger])
            self.update_timer.start()
        else:
            # Schedule for tomorrow
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
            delay = (tomorrow - now).total_seconds()
            
            self.stat_str = f"No more updates today. Scheduling for tomorrow at {tomorrow.strftime('%H:%M:%S')}"
            print(self.stat_str)
            
            if self.update_timer:
                self.update_timer.cancel()
                
            self.update_timer = threading.Timer(delay, self._start_new_day)
            self.update_timer.start()
        
    def _perform_update(self, trigger:UpdateTrigger):
        """Perform the scheduled update"""
        if not self.running:
            return
            
        print(f"Update triggered: {trigger.value}")
        
        # alarm
        if trigger == UpdateTrigger.TASK_START and not self._in_silent_hour():
            now = datetime.now() + timedelta(seconds=1) # or it won't get to current task.
            today_tasks = self.routine.create_schedule(date.today())        #TODO This is not clean.
            curr_task:Task = find_current_task(today_tasks, now)
            if curr_task and curr_task.has_alarm:
                print(f'Playing alarm {curr_task.alarm_sound} for {curr_task.title}')
                bark(curr_task.alarm_sound)

        # update display
        self._update_display(no_display=self._in_silent_hour())
        self.last_update = datetime.now()
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
        self.routine = self._get_today_routine() 
        self._schedule_today_updates()
        self._perform_update(UpdateTrigger.TASK_START)
        
    def _update_display(self, no_display:bool=False):
        """Update display and save preview"""
        img = self.renderer.create_schedule_image(self.routine)
        if not no_display:
            display.set_image(img)

        out_path = os.path.join(BASE_DIR, 'output')
        if not os.path.exists(out_path): os.mkdir(out_path)
        img.save(os.path.join(out_path, 'schedule_preview.png'))
        
        # Update current task/panels tracking
        now = datetime.now()
        today_tasks = self.routine.create_schedule(date.today())
        self.current_task = find_current_task(today_tasks, now)
        self.current_panels = get_timeline_panel_ranges(now)
        
        status = " (silent)" if no_display else ""
        print(f"Preview saved at {now.strftime('%H:%M:%S')}{status}")
                
    def stop(self):
        self.running = False
        if self.update_timer:
            self.update_timer.cancel()
        self.stop_event.set()
        print("Daemon stopped")

    def _get_today_routine(self):
        """Get routine for current date"""
        today_key = datetime.now().strftime('%m%d')
        return routines.get(today_key, rt_workday)
    
    def _in_silent_hour(self, dt=None):
        """Check if time is in silent hours (no display updates or alarms)"""
        if dt is None:
            dt = datetime.now()
        hour = dt.hour
        
        if self.silent_start_hour < self.silent_end_hour:
            return self.silent_start_hour <= hour < self.silent_end_hour
        else:
            return hour >= self.silent_start_hour or hour < self.silent_end_hour
    
    def _is_task_trigger(self, trigger):
        """Check if trigger is task-related (high priority)"""
        return trigger in [UpdateTrigger.TASK_START, UpdateTrigger.TASK_END]

def signal_handler(signum, frame):
    global daemon
    if daemon:
        daemon.stop()
    sys.exit(0)

if __name__ == "__main__":
    daemon = ScheduleDaemon()
    signal.signal(signal.SIGINT, signal_handler)
    daemon.start()