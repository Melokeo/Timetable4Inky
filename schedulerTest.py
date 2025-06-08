import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date

import scheduler
from scheduler import ScheduleDaemon, UpdateTrigger
from task import Task, Sound, Tag


class FakeRoutine:
    """A fake routine that returns a predefined list of tasks."""
    def __init__(self, tasks):
        self._tasks = tasks

    def create_schedule(self, date_arg):
        return list(self._tasks)  # Return a copy to avoid mutation side‐effects


class TestScheduleDaemon(unittest.TestCase):
    def setUp(self):
        # Freeze “now” to 2025-06-01 09:00:00 for all tests
        self.fixed_now = real_datetime(2025, 6, 1, 9, 0, 0)

        class FakeDateTime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return self.fixed_now

        class FakeDate(real_date):
            @classmethod
            def today(cls):
                return self.fixed_now.date()

        # Patch scheduler.datetime and scheduler.date so ScheduleDaemon uses fixed “now”
        patcher_dt = patch.object(scheduler, 'datetime', FakeDateTime)
        patcher_date = patch.object(scheduler, 'date', FakeDate)
        self.addCleanup(patcher_dt.stop)
        self.addCleanup(patcher_date.stop)
        patcher_dt.start()
        patcher_date.start()

        # Create a fresh daemon for each test
        self.daemon = ScheduleDaemon()
        # Make periodic_interval large by default so fill‐periodic adds nothing unless overridden
        self.daemon.periodic_interval = real_timedelta(hours=24)

    def test_no_tasks_schedules_only_panel_shift(self):
        """If there are no tasks, only a PANEL_SHIFT at 12:00 should be queued (no periodic)."""
        self.daemon.routine = FakeRoutine(tasks=[])
        self.daemon.min_interval = real_timedelta(minutes=1)

        self.daemon._schedule_today_updates()

        # Expect exactly one entry: PANEL_SHIFT at 12:00:00.000001
        expected_time = self.fixed_now.replace(hour=12, minute=0, second=0, microsecond=1)
        queue = list(self.daemon.update_queue)
        self.assertEqual(len(queue), 1)
        sched_time, trigger = queue[0]
        self.assertEqual(sched_time, expected_time)
        self.assertEqual(trigger, UpdateTrigger.PANEL_SHIFT)

    def test_single_task_scheduling(self):
        """A single task should produce exactly TASK_START, TASK_END, and PANEL_SHIFT if not filtered."""
        # Task at 09:05 for 10 minutes → ends at 09:15
        t1_start = self.fixed_now + real_timedelta(minutes=5)
        t1 = Task(
            title='Task1',
            start_time=t1_start,
            duration=real_timedelta(minutes=10),
            has_alarm=False,
            has_end_alarm=False
        )
        self.daemon.routine = FakeRoutine(tasks=[t1])
        self.daemon.min_interval = real_timedelta(minutes=1)

        self.daemon._schedule_today_updates()
        queue = sorted(self.daemon.update_queue)

        expected = [
            (t1_start, UpdateTrigger.TASK_START),
            (t1_start + real_timedelta(minutes=10), UpdateTrigger.TASK_END),
            (self.fixed_now.replace(hour=12, minute=0, second=0, microsecond=1), UpdateTrigger.PANEL_SHIFT)
        ]
        self.assertEqual(queue, expected)

    def test_task_min_interval_filtering(self):
        """
        If a TASK_END is within min_interval of any TASK_START, it should be dropped.
        Example: Task1 starts 09:01 ends 09:02; Task2 starts 09:03 ends 09:04.
        With min_interval = 3 minutes, both end‐times are dropped.
        """
        t1_start = self.fixed_now + real_timedelta(minutes=1)   # 09:01
        t1 = Task(
            title='T1',
            start_time=t1_start,
            duration=real_timedelta(minutes=1),  # ends at 09:02
            has_alarm=False,
            has_end_alarm=False
        )
        t2_start = self.fixed_now + real_timedelta(minutes=3)   # 09:03
        t2 = Task(
            title='T2',
            start_time=t2_start,
            duration=real_timedelta(minutes=1),  # ends at 09:04
            has_alarm=False,
            has_end_alarm=False
        )
        self.daemon.routine = FakeRoutine(tasks=[t1, t2])
        self.daemon.min_interval = real_timedelta(minutes=3)

        self.daemon._schedule_today_updates()
        queue = sorted(self.daemon.update_queue)

        expected = [
            (t1_start, UpdateTrigger.TASK_START),
            (t2_start, UpdateTrigger.TASK_START),
            (self.fixed_now.replace(hour=12, minute=0, second=0, microsecond=1), UpdateTrigger.PANEL_SHIFT)
        ]
        self.assertEqual(queue, expected)

    def test_alarm_trigger_on_task_start_and_end(self):
        """
        Verify that when a TASK_START or TASK_END is performed, bark() is called
        if has_alarm or has_end_alarm is True (outside silent hours), and not called during silent hours.
        """
        # Task at 09:00:10 lasting 5 seconds → ends at 09:00:15
        start_time = self.fixed_now + real_timedelta(seconds=10)
        duration = real_timedelta(seconds=5)
        t1 = Task(
            title='AlarmTask',
            start_time=start_time,
            duration=duration,
            has_alarm=True,
            alarm_sound=Sound.DEFAULT,
            has_end_alarm=True,
            end_alarm_sound=Sound._173
        )
        self.daemon.routine = FakeRoutine(tasks=[t1])
        self.daemon.min_interval = real_timedelta(minutes=1)
        self.daemon.running = True  # Must be True for _perform_update to proceed

        # Stub out side‐effects
        with patch.object(ScheduleDaemon, '_update_display'), \
             patch.object(ScheduleDaemon, '_schedule_next_update'), \
             patch.object(self.daemon.uploader, 'upload_png', return_value=None), \
             patch.object(scheduler, 'find_current_task', return_value=t1):

            bark_calls = []
            def fake_bark(sound):
                bark_calls.append(sound)

            with patch.object(scheduler, 'bark', side_effect=fake_bark):
                # 1) Trigger TASK_START outside silent hours (09:00)
                self.daemon._perform_update(UpdateTrigger.TASK_START)
                self.assertEqual(bark_calls[-1], Sound.DEFAULT)

                # 2) Trigger TASK_END outside silent hours
                self.daemon._perform_update(UpdateTrigger.TASK_END)
                self.assertEqual(bark_calls[-1], Sound._173)

                # 3) Simulate silent hour by patching datetime.now to 02:00
                silent_time = real_datetime(2025, 6, 1, 2, 0, 0)
                class SilentDateTime(real_datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return silent_time

                with patch.object(scheduler, 'datetime', SilentDateTime):
                    bark_calls.clear()
                    # In silent hours, no bark for TASK_START or TASK_END
                    self.daemon._perform_update(UpdateTrigger.TASK_START)
                    self.daemon._perform_update(UpdateTrigger.TASK_END)
                    self.assertEqual(len(bark_calls), 0)

    def test_periodic_fill_after_last_task(self):
        """
        If there is one task and periodic_interval is 30 minutes, ensure periodic updates fill after the task end.
        """
        t1_start = self.fixed_now + real_timedelta(minutes=5)  # 09:05
        t1 = Task(
            title='PTask',
            start_time=t1_start,
            duration=real_timedelta(minutes=1),  # ends 09:06
            has_alarm=False,
            has_end_alarm=False
        )
        self.daemon.routine = FakeRoutine(tasks=[t1])
        self.daemon.periodic_interval = real_timedelta(minutes=30)
        self.daemon.min_interval = real_timedelta(minutes=1)

        self.daemon._schedule_today_updates()
        queue = sorted(self.daemon.update_queue)

        # First two must be TASK_START @09:05, TASK_END @09:06
        self.assertEqual(queue[0], (t1_start, UpdateTrigger.TASK_START))
        self.assertEqual(queue[1], (t1_start + real_timedelta(minutes=1), UpdateTrigger.TASK_END))

        # The next periodic event should occur at t1_end + 30 minutes → 09:36 (ignoring seconds)
        first_periodic = next(item for item in queue if item[1] == UpdateTrigger.PERIODIC)
        self.assertEqual(first_periodic[0].hour, 9)
        self.assertEqual(first_periodic[0].minute, 36)

    def test_new_day_not_scheduled_in_original_code(self):
        """
        Confirm that NEW_DAY is not appended, since scheduler.py calculates next_midnight
        but never adds (next_midnight, NEW_DAY) to candidates.
        """
        t1 = Task(
            title='AnyTask',
            start_time=self.fixed_now + real_timedelta(minutes=5),
            duration=real_timedelta(minutes=5),
            has_alarm=False,
            has_end_alarm=False
        )
        self.daemon.routine = FakeRoutine(tasks=[t1])
        self.daemon.min_interval = real_timedelta(minutes=1)

        self.daemon._schedule_today_updates()
        triggers = {trigger for _, trigger in self.daemon.update_queue}
        self.assertNotIn(UpdateTrigger.NEW_DAY, triggers)


if __name__ == '__main__':
    unittest.main()
