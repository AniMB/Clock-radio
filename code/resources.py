import threading


global _lock
_lock = threading.Lock()