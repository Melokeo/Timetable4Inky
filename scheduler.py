#!/usr/bin/env python3
import time
import threading
from datetime import datetime, timedelta, date, time as dtime
from enum import Enum
import os
import sys
import heapq
import signal
from PIL import Image   # to read img

# local modules
from draw import TotalRenderer, get_timeline_panel_ranges
from routines import rt_workday, routines
from task import find_current_task, Task, TaskStat
from uploader import TimelineUploader
from display import display, INKY_AVAILABLE
from alarm import Sound, bark, shut_up
from btnListener import BtnListener

if INKY_AVAILABLE:
    from display import true_display

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
daemon = None

class UpdateTrigger(Enum):
    TASK_END    = "task_end"
    TASK_START  = "task_start" 
    PANEL_SHIFT = "panel_shift"
    PERIODIC    = "periodic"
    NEW_DAY     = "new_day"     # reserved; not used.
    BTN_EVT     = 'button_event'
    BOLUS       = 'bolus'       # reserved

class ScheduleDaemon:
    def __init__(self):
        self.routine = None
        self.last_update = datetime.now()
        self.task_instances = None
        self.current_task = None
        self.current_panels = None
        self.running = False
        self.min_interval = timedelta(minutes=3, seconds=1)
        self.periodic_interval = timedelta(minutes=30)
        self.renderer = TotalRenderer()
        self.uploader = TimelineUploader(os.path.join(BASE_DIR, 'cfg', 'upload_config.json'))
        self.update_timer = None
        self.update_queue: list[tuple[datetime, UpdateTrigger]] = [] 
        self.stop_event = threading.Event()
        self.stat_str = ''
        self.silent_hrs: list[tuple[dtime]] = [(dtime(0, 10), dtime(6, 30)), (dtime(9, 30), dtime(17, 30))]
        self.silent_hrs_wkday: list[tuple[dtime]] = [(dtime(0, 5), dtime(6, 40)), (dtime(9, 20), dtime(17, 40))]
        self.silent_hrs_wkend: list[tuple[dtime]] = [(dtime(0, 5), dtime(7, 00))]

        self.btnListener = BtnListener(callback=self.on_button)
        self.btn_evt_interval = 0.75 # mins
        self.btn_update_timer: threading.Timer = None

        self.special_trigger: list[UpdateTrigger] = [UpdateTrigger.BOLUS, UpdateTrigger.BTN_EVT]
        # special trigger that is set halfway and 
        # omitting this will lead to loss of already planned triggers in _schedule_next_update()
        
    def start(self):
        self.running = True
        self.routine = self._get_today_routine()
        print("Schedule daemon started")
        
        self._schedule_today_updates()
        self._schedule_next_update()
        
        # initial update
        self.uploader.upload_png(note=self.stat_str)
        time.sleep(1)
        self._update_display()

        bark(Sound.OB_STAC)
        
        # allow keybd interrupt
        while self.running:
            self.stop_event.wait(timeout=1) # or it won't stop on ^C
            if self.stop_event.is_set():
                break
    
    def has_close_updates(self, time_to_check:datetime=None, interval_multiplier:float=1):
        time_to_check = time_to_check or datetime.now()
        has_close_update = any(
                    (t - time_to_check).total_seconds() < \
                    self.min_interval.total_seconds() \
                    for t, _ in self.update_queue
                )
        is_too_frequent = (time_to_check - self.last_update).total_seconds() < self.min_interval.total_seconds()
        return has_close_update # or is_too_frequent

    def _schedule_today_updates(self):
        """Pre-calculate all update times for today"""
        now = datetime.now()
        self.task_instances = self.routine.create_schedule(date.today())
        self.silent_hrs = self.silent_hrs_wkday if datetime.now().weekday()<5 else self.silent_hrs_wkend
        print(f'{self.silent_hrs=}')

        self.update_queue = []
        candidates = []

        for task in self.task_instances:
            if task.start_time > now:       # always add task start trigger
                candidates.append((task.start_time, UpdateTrigger.TASK_START))
            task_end = task.start_time + task.duration
            if task_end > now:
                if not self.has_close_updates(task_end):     # if no conflict then append task end trigger
                    candidates.append((task_end, UpdateTrigger.TASK_END))

        panel_time = now.replace(hour=12, minute=0, second=0, microsecond=1)
        if panel_time > now:
            if not self.has_close_updates(panel_time):
                candidates.append((panel_time, UpdateTrigger.PANEL_SHIFT))

        # add NEW_DAY at 00:00 tomorrow
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=1)

        # filter out events too close to TASK_START or next midnight        -- double check unnecessary
        starts = [t for t, k in candidates if k == UpdateTrigger.TASK_START]
        final = []
        for t, k in candidates:
            too_close_to_start = k != UpdateTrigger.TASK_START and any(
                abs((t - s).total_seconds()) < self.min_interval.total_seconds() for s in starts
            )
            too_close_to_midnight = \
                k != UpdateTrigger.NEW_DAY and \
                abs((t - next_midnight).total_seconds()) < self.min_interval.total_seconds()
            if not too_close_to_start and not too_close_to_midnight:
                final.append((t, k))

        for t, k in sorted(final):
            heapq.heappush(self.update_queue, (t, k))
        self._schedule_fill_periodic(self.task_instances, now)

        self.print_update_queue()
    
    def print_update_queue(self, queue:list[tuple[datetime,UpdateTrigger]]=None):
        queue = queue or self.update_queue
        print("Update Queue:")
        for t, k in sorted(self.update_queue):
            print(f"  {t.strftime('%H:%M:%S')}  |  {k.value}")

    def on_button(self, label) -> None:
        # print(f"Button {label} pressed")
        if label == 'B':
            shut_up()
            return
        
        # following btn events requires update scheduled
        if label == 'A':
            if self.current_task:
                self.current_task.curr_status = TaskStat.ONGOING
        elif label == 'C':
            if self.current_task:
                self.current_task.curr_status = TaskStat.IGNORED

        bark(Sound.OB_STAC)

        # check if any updates are scheduled within 10 mins
        now = datetime.now()
        is_too_frequent =  (now - self.last_update).total_seconds()
        if is_too_frequent:
            now = now + self.min_interval          # not accurate but acceptable
        if not self.has_close_updates(time_to_check=now, interval_multiplier=2):
            update_time = now + timedelta(minutes = self.btn_evt_interval)
            if not self.btn_update_timer:
                self.btn_update_timer = threading.Timer(self.btn_evt_interval*60, self._perform_update, args=[UpdateTrigger.BTN_EVT])
                self.btn_update_timer.start()
                self.stat_str = f"Inserted btn update at {update_time.strftime('%H:%M:%S')}"
                print(self.stat_str)
            else:
                print('Btn update already exists')
        else:
            print('Btn event update overridden')

        # self.print_update_queue()

        self._update_display(no_display=True)
        self.uploader.upload_png(note=self.stat_str+' [status change]')

        return

    def _schedule_fill_periodic(self, tasks:list[Task], now:datetime) -> None:
        """Fill gaps between task events with periodic updates"""
        # get all future task events, sorted
        events:list[datetime] = []
        for task in tasks:
            task:Task
            if task.start_time > now:
                events.append(task.start_time)
            task_end = task.start_time + task.duration  
            if task_end > now:
                events.append(task_end)
        
        events.sort()
        end_day = now.replace(hour=23, minute=59)
        
        if not events:
            # no events: fill every periodic_interval until end of day
            t = now + self.periodic_interval
            while t < end_day - self.min_interval:
                heapq.heappush(self.update_queue, (t, UpdateTrigger.PERIODIC))
                t += self.periodic_interval
            return
        
        # fill from now→first event
        t = now + self.periodic_interval
        while t < events[0] - self.min_interval:
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
        '''Start a timer for next update. IMPORTANT: it removes earliest trigger from queue'''
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
                if not self.has_close_updates(earliest_allowed):
                    temp_queue.append((earliest_allowed, trigger))
        
        # put back any rescheduled items
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
        # print(f"Trigger Check: {trigger==UpdateTrigger.TASK_START or trigger == UpdateTrigger.TASK_END} | {'Muted' if self._in_silent_hour() else 'BarkOK'}")
        if trigger == UpdateTrigger.TASK_START and not self._in_silent_hour():
            now = datetime.now() + timedelta(seconds=1) # or it won't get to current task.
            today_tasks = self.routine.create_schedule(date.today())        #TODO This is not clean.
            curr_task:Task = find_current_task(today_tasks, now)
            # print(curr_task, f'{curr_task.has_alarm = }')
            if curr_task and curr_task.has_alarm: 
                print(f'Playing alarm {curr_task.alarm_sound} for {curr_task.title}')
                bark(curr_task.alarm_sound)
        elif trigger == UpdateTrigger.TASK_END and not self._in_silent_hour():
            now = datetime.now() + timedelta(seconds=1) # or it won't get to current task??
            today_tasks = self.routine.create_schedule(date.today())        #TODO This is not clean.
            curr_task:Task = find_current_task(today_tasks, now)
            if curr_task and curr_task.has_end_alarm:
                print(f'Playing alarm {curr_task.end_alarm_sound} for {curr_task.title}')
                bark(curr_task.end_alarm_sound)

        # update display
        self._update_display(no_display=self._in_silent_hour())
        self.last_update = datetime.now()
        self.btn_update_timer = None
        if not trigger in self.special_trigger:
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
        # self.task_instances = self.routine.create_schedule(date.today())
        self._schedule_today_updates()
        self._perform_update(UpdateTrigger.TASK_START)
        
    def _update_display(self, no_display:bool=False):
        """Update display and save preview"""
        # update current task/panels tracking
        now = datetime.now()
        self.current_task = find_current_task(self.task_instances, now)
        self.current_panels = get_timeline_panel_ranges(now)    
        
        # update display
        img = self.renderer.create_schedule_image(self.routine, self.task_instances)
        if not no_display:
            display.set_image(img)

        out_path = os.path.join(BASE_DIR, 'output')
        if not os.path.exists(out_path): os.mkdir(out_path)
        img.save(os.path.join(out_path, 'schedule_preview.png'))

        if INKY_AVAILABLE and not no_display:
            img_disp = Image.open(os.path.join(out_path, 'schedule_preview.png'))
            true_display.set_image(img_disp)
            true_display.show()

        
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
        t = dt.time()
        return any(start <= t < end if start < end else t >= start or t < end for start, end in self.silent_hrs)

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