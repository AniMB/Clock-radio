import _thread


global _lock
_lock = _thread.allocate_lock()



global json_obj
json_obj = {
  "alarm_hour": 0,
  "alarm_minute": 0,
  "alarm_ampm": 0,
  "freq1": 101.9,
  "freq2": 101.9,
  "freq3": 101.9,
  "volume": 50,
  "nowplaying": 1,
  "use24Hour": 1,
  "mute": 0,
  "Time": "12:00:00",
  "time_ampm": 0,
  "snooze": 5,
  "cancelAlarm": 0
}
