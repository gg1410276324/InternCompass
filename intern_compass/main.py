import sys
from tkinter import messagebox

from data_loader import DataLoadError, load_all_data


def main():
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        messagebox.showerror(
            "缺少依赖",
            "当前环境没有安装 CustomTkinter。\n请先运行：pip install customtkinter\n然后再执行：python main.py",
        )
        sys.exit(1)

    from ui_components import InternCompassApp

    try:
        data = load_all_data()
    except DataLoadError as exc:
        messagebox.showerror("配置读取失败", str(exc))
        sys.exit(1)

    app = InternCompassApp(
        jobs=data["jobs"],
        options_config=data["options"],
        rules_config=data["rules"],
    )
    app.mainloop()


if __name__ == "__main__":
    main()
