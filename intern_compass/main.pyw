from datetime import datetime
from pathlib import Path
import os
import sys
import traceback


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app_error.log"


def _write_error_log(error):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write("\n==== Intern Compass error ====\n")
        file.write(f"Time: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"Working directory: {os.getcwd()}\n")
        file.write(f"Error: {error!r}\n")
        file.write(traceback.format_exc())
        file.write("\n")


def _show_error_message():
    try:
        from tkinter import messagebox

        messagebox.showerror(
            "Intern Compass 启动失败",
            f"程序启动失败，错误信息已写入：\n{LOG_FILE}",
        )
    except Exception:
        pass


try:
    os.chdir(BASE_DIR)
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from main import main

    main()
except SystemExit as exc:
    if exc.code not in (None, 0):
        _write_error_log(exc)
    raise
except BaseException as exc:
    _write_error_log(exc)
    _show_error_message()
