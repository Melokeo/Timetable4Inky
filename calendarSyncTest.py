from calendarSync import CalendarSync
from datetime import date, timedelta
from pathlib import Path
from abbrGPT import abbreviateBatch

def test_outlook_subscription():
    config_dir = Path(__file__).parent / "cfg" / "calendars"
    sync = CalendarSync(str(config_dir))

    tasks = []
    days_checked = 0
    offset = 0

    while not tasks and days_checked < 30:
        for delta in [offset, -offset] if offset else [0]:
            check_date = date.today() + timedelta(days=delta)
            fetched = sync.fetch_tasks_for_date(check_date)
            if fetched:
                tasks = fetched
                print(f"Fetched {len(tasks)} tasks for {check_date}:")
                tasks = abbreviateBatch([t.title for t in tasks])
                '''for task in tasks:
                    print("-", task)'''
                print(tasks)
                return
        offset += 1
        days_checked += 1

    print("Get into calendar but no tasks found in the ±30 day window.")

def test_google_calendar():
    """Test Google Calendar connection and fetch example events"""
    print("=== Testing Google Calendar Connection ===")

    from googleCalender import GoogleCalendarAdapter
    
    config_dir = Path(__file__).parent / "cfg" / "calendars"
    sync = CalendarSync(str(config_dir))
    print(f'cfg_dir = {config_dir}')
    
    # Find Google Calendar adapter from loaded configs
    adapter = None
    print(sync.adapters)
    for adp in sync.adapters:
        if adp.config.source_type == 'google_api':
            adapter = adp
            break
    
    if not adapter:
        print("✗ No Google Calendar configuration found in cfg/calendars/")
        return
    
    try:
        print("✓ Google Calendar connection successful")
        
        # Test 1: Fetch available calendars
        print("\n=== Available Calendars ===")
        calendars = adapter.get_calendar_list()
        if calendars:
            for cal in calendars[:5]:  # Show first 5
                primary = " (PRIMARY)" if cal.get('primary') else ""
                print(f"- {cal['name']}{primary}")
                print(f"  ID: {cal['id']}")
        else:
            print("No calendars found")
        
        # Test 2: Fetch events for today and nearby dates
        print("\n=== Fetching Events ===")
        tasks = []
        days_checked = 0
        offset = 0
        
        while not tasks and days_checked < 14:
            for delta in [offset, -offset] if offset else [0]:
                check_date = date.today() + timedelta(days=delta)
                fetched = adapter.fetch_tasks_for_date(check_date)
                if fetched:
                    tasks = fetched
                    print(f"Found {len(tasks)} events for {check_date}:")
                    
                    # Show first few events
                    for task in tasks[:3]:
                        time_str = task.start_time.strftime('%H:%M')
                        print(f"  {time_str} - {task.title}")
                        if task.description:
                            desc = task.description[:50] + "..." if len(task.description) > 50 else task.description
                            print(f"    Description: {desc}")
                    
                    if len(tasks) > 3:
                        print(f"    ... and {len(tasks) - 3} more events")
                    return
            offset += 1
            days_checked += 1
        
        print("No events found in the ±14 day window.")
        
    except FileNotFoundError as e:
        print(f"✗ Configuration file missing: {e}")
        print("Please ensure credentials.json is in cfg/ directory")
    except Exception as e:
        print(f"✗ Google Calendar test failed: {e}")

def test_google_calendar_bulk():
    """Test Google Calendar connection and fetch example events"""
    print("=== Testing Google Calendar Connection ===")

    config_dir = Path(__file__).parent / "cfg" / "calendars"
    sync = CalendarSync(str(config_dir))
    
    # Find Google Calendar adapter
    adapter = None
    for adp in sync.adapters:
        if adp.config.source_type == 'google_api':
            adapter = adp
            break
    
    if not adapter:
        print("✗ No Google Calendar configuration found")
        return
    
    try:
        print("✓ Google Calendar connection successful")
        
        # Test: Fetch events for today and nearby dates
        print("\n=== Fetching Events ===")
        all_tasks = []
        days_checked = 0
        offset = 0
       
        while days_checked < 20:
            for delta in [offset, -offset] if offset else [0]:
                check_date = date.today() + timedelta(days=delta)
                fetched = adapter.fetch_tasks_for_date(check_date)
                if fetched:
                    all_tasks.extend(fetched)
            offset += 1
            days_checked += 1
       
        if all_tasks:
            print(f"Found {len(all_tasks)} total events across {days_checked} days:")
            titles = [task.title for task in all_tasks]
            abbr_titles = abbreviateBatch(titles)
            print(abbr_titles)
        else:
            print("No events found in the ±60 day window.")
        
    except Exception as e:
        print(f"✗ Google Calendar test failed: {e}")

if __name__ == "__main__":
    # test_outlook_subscription()
    test_google_calendar_bulk()