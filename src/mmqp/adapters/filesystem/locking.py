import fcntl
from dataclasses import dataclass
from pathlib import Path
from typing import IO


@dataclass
class FileLock:
    path: Path
    exclusive: bool = True
    handle: IO[str] | None = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH)

    def release(self) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None
