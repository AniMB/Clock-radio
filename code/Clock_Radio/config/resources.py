import _thread


global _lock
_lock = _thread.allocate_lock()