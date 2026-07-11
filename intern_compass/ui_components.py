import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from data_manager import save_user_run
from debug_logger import log_event
from knowledge_base import conditional_group_for_major, find_major, major_group_for_major, normalize_major, search_majors
from report_generator import export_report
from rules import calculate_recommendations, group_jobs_by_category, search_jobs
from ui_config import UI_CONFIG


RESULT_BATCH_SIZE = 10
SEARCH_BATCH_SIZE = 20
JOB_MAP_BATCH_SIZE = 60
SEARCH_DEBOUNCE_MS = 300


def _write_error_log(error):
    try:
        try:
            from app_paths import writable_path
            log_file = writable_path("logs/app_error.log")
            log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            logs_dir = Path(__file__).resolve().parent / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "app_error.log"
        with log_file.open("a", encoding="utf-8") as file:
            file.write("\n==== Intern Compass runtime error ====\n")
            file.write(f"Error type: {type(error).__name__}\n")
            file.write(f"Error: {error!r}\n")
            file.write(traceback.format_exc())
            file.write("\n")
        return log_file
    except Exception:
        return None


def _run_daemon(target):
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def _job_display_name(job):
    return job.get("display_name") or job.get("job_name", "")


def _layout(key, fallback=None):
    return UI_CONFIG["layout"].get(key, fallback)


def _button_style(kind="primary"):
    style = dict(UI_CONFIG.get("buttons_style", {}).get(kind, UI_CONFIG["buttons_style"]["primary"]))
    style["corner_radius"] = _layout("button_radius", 10)
    return style


def _entry_style():
    return {
        "fg_color": UI_CONFIG["theme"]["panel"],
        "border_color": UI_CONFIG["theme"]["border"],
        "border_width": 1,
        "text_color": UI_CONFIG["theme"]["text"],
        "placeholder_text_color": UI_CONFIG["theme"]["subtle"],
        "corner_radius": _layout("input_radius", 8),
    }


def _option_menu_style():
    return {
        "fg_color": UI_CONFIG["dropdown"]["fg_color"],
        "border_width": UI_CONFIG["dropdown"]["border_width"],
        "border_color": UI_CONFIG["dropdown"]["border_color"],
        "text_color": UI_CONFIG["dropdown"]["text_color"],
        "arrow_color": UI_CONFIG["dropdown"]["arrow_color"],
        "button_color": UI_CONFIG["dropdown"]["button_color"],
        "button_hover_color": UI_CONFIG["dropdown"]["button_hover_color"],
        "dropdown_fg_color": UI_CONFIG["dropdown"]["dropdown_fg_color"],
        "dropdown_hover_color": UI_CONFIG["theme"]["panel_alt"],
        "dropdown_text_color": UI_CONFIG["dropdown"]["dropdown_text_color"],
        "corner_radius": UI_CONFIG["dropdown"]["corner_radius"],
    }


def _create_badge(master, text, color=None, bg=None, font_key="small", height=24):
    return ctk.CTkLabel(
        master,
        text=text,
        text_color=color or UI_CONFIG["theme"]["tag_text"],
        fg_color=bg or UI_CONFIG["theme"]["tag_bg"],
        corner_radius=999,
        font=_font(font_key),
        height=height,
    )


def _bind_wrap(label, min_width=180, horizontal_padding=24, max_width=None):
    # Keep wraplength stable. Updating it from repeated <Configure> events can
    # lock Tk's layout loop in scrollable panes.
    wrap = max(min_width, 260 - horizontal_padding)
    if max_width is not None:
        wrap = min(max_width, wrap)
    label._last_wraplength = wrap
    label.configure(wraplength=wrap)
    return label

def _tag_row(master, values, max_items=None):
    row = ctk.CTkFrame(master, fg_color="transparent")
    shown = list(values or [])
    if max_items:
        shown = shown[:max_items]
    for index, value in enumerate(shown):
        _create_badge(row, str(value)).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 6), pady=(0, 6), ipadx=7)
    return row


def _create_panel_heading(master, title, subtitle=None, icon_text=None):
    frame = ctk.CTkFrame(master, fg_color="transparent")
    frame.grid_columnconfigure(1, weight=1)
    if icon_text:
        ctk.CTkLabel(
            frame,
            text=icon_text,
            width=30,
            height=30,
            fg_color=UI_CONFIG["theme"]["primary_soft"],
            text_color=UI_CONFIG["theme"]["primary"],
            corner_radius=10,
            font=_font("subtitle"),
        ).grid(row=0, column=0, rowspan=2 if subtitle else 1, sticky="n", padx=(0, 10))
    title_column = 1 if icon_text else 0
    ctk.CTkLabel(frame, text=title, font=_font("panel_title"), text_color=UI_CONFIG["theme"]["text"]).grid(row=0, column=title_column, sticky="w")
    if subtitle:
        ctk.CTkLabel(frame, text=subtitle, font=_font("small"), text_color=UI_CONFIG["theme"]["muted"]).grid(row=1, column=title_column, sticky="w", pady=(2, 0))
    return frame


def _create_section_card(master, title, icon_text=None):
    pad = UI_CONFIG["layout"]["padding_md"]
    card = ctk.CTkFrame(
        master,
        fg_color=UI_CONFIG["theme"]["panel"],
        corner_radius=UI_CONFIG["layout"]["card_radius"],
        border_width=1,
        border_color=UI_CONFIG["theme"]["border"],
    )
    card.columnconfigure(0, weight=1)
    _create_panel_heading(card, title, icon_text=icon_text).grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 8))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.grid(row=1, column=0, sticky="ew", padx=pad, pady=(0, pad))
    body.columnconfigure(0, weight=1)
    return card, body


def _level_colors(level):
    return UI_CONFIG["levels"].get(level, {
        "display": level or "岗位方向",
        "color": UI_CONFIG["theme"]["tag_text"],
        "bg": UI_CONFIG["theme"]["tag_bg"],
        "border": UI_CONFIG["theme"]["border"],
    })


def _relevance_colors(value):
    text = value or "低专业限制"
    for key, colors in UI_CONFIG["relevance"].items():
        if key != "默认" and key in text:
            return colors
    return UI_CONFIG["relevance"]["默认"]


class BorderedArrowOptionMenu(ctk.CTkOptionMenu):
    def __init__(self, *args, border_width=None, border_color=None, arrow_color=None, **kwargs):
        dropdown_style = UI_CONFIG["dropdown"]
        self._dropdown_border_width = dropdown_style["border_width"] if border_width is None else border_width
        self._dropdown_border_color = dropdown_style["border_color"] if border_color is None else border_color
        self._arrow_color = dropdown_style["arrow_color"] if arrow_color is None else arrow_color
        super().__init__(*args, **kwargs)

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)

        left_section_width = self._current_width - self._current_height
        requires_recoloring = self._draw_engine.draw_rounded_rect_with_border_vertical_split(
            self._apply_widget_scaling(self._current_width),
            self._apply_widget_scaling(self._current_height),
            self._apply_widget_scaling(self._corner_radius),
            self._apply_widget_scaling(self._dropdown_border_width),
            self._apply_widget_scaling(left_section_width),
        )

        if no_color_updates is False or requires_recoloring:
            border_color = self._apply_appearance_mode(self._dropdown_border_color)
            self._canvas.itemconfig("border_parts_left", outline=border_color, fill=border_color)
            self._canvas.itemconfig("border_parts_right", outline=border_color, fill=border_color)
            self._canvas.itemconfig("dropdown_arrow", fill=self._apply_appearance_mode(self._arrow_color))

    def configure(self, require_redraw=False, **kwargs):
        if "border_width" in kwargs:
            self._dropdown_border_width = kwargs.pop("border_width")
            require_redraw = True
        if "border_color" in kwargs:
            self._dropdown_border_color = kwargs.pop("border_color")
            require_redraw = True
        if "arrow_color" in kwargs:
            self._arrow_color = kwargs.pop("arrow_color")
            require_redraw = True
        super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name):
        if attribute_name == "border_width":
            return self._dropdown_border_width
        if attribute_name == "border_color":
            return self._dropdown_border_color
        if attribute_name == "arrow_color":
            return self._arrow_color
        return super().cget(attribute_name)


class BorderedArrowComboBox(ctk.CTkComboBox):
    def __init__(self, *args, arrow_color=None, **kwargs):
        self._arrow_color = UI_CONFIG["dropdown"]["arrow_color"] if arrow_color is None else arrow_color
        super().__init__(*args, **kwargs)

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        border_color = self._apply_appearance_mode(self._border_color)
        self._canvas.itemconfig("border_parts_right", fill=border_color, outline=border_color)
        self._canvas.itemconfig("dropdown_arrow", fill=self._apply_appearance_mode(self._arrow_color))

    def configure(self, require_redraw=False, **kwargs):
        if "arrow_color" in kwargs:
            self._arrow_color = kwargs.pop("arrow_color")
            require_redraw = True
        super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name):
        if attribute_name == "arrow_color":
            return self._arrow_color
        return super().cget(attribute_name)


class MultiSelectGroup(ctk.CTkFrame):
    def __init__(self, master, title, options, columns=2):
        super().__init__(
            master,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["card_radius"],
            border_width=1,
            border_color=UI_CONFIG["theme"]["border"],
        )
        self.variables = {}
        self.columns = columns
        for column in range(columns):
            self.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(self, text=title, font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"]).grid(
            row=0,
            column=0,
            columnspan=columns,
            sticky="w",
            padx=12,
            pady=(12, 8),
        )
        for index, option in enumerate(options, start=1):
            var = tk.BooleanVar(value=False)
            self.variables[option] = var
            checkbox = ctk.CTkCheckBox(
                self,
                text=option,
                variable=var,
                font=_font("small"),
                checkbox_width=18,
                checkbox_height=18,
                text_color=UI_CONFIG["theme"]["text"],
                fg_color=UI_CONFIG["theme"]["primary"],
                hover_color=UI_CONFIG["theme"]["primary_hover"],
                border_color=UI_CONFIG["theme"]["border_strong"],
            )
            checkbox.grid(
                row=(index - 1) // columns + 1,
                column=(index - 1) % columns,
                sticky="w",
                padx=12,
                pady=(2, 6),
            )

    def get_selected(self):
        return [label for label, variable in self.variables.items() if variable.get()]

    def clear(self):
        for variable in self.variables.values():
            variable.set(False)


class StudentProfileForm(ctk.CTkScrollableFrame):
    def __init__(self, master, options_config, on_generate, on_clear, on_show_map):
        super().__init__(
            master,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["corner_radius"],
            border_width=UI_CONFIG["layout"]["border_width"],
            border_color=UI_CONFIG["theme"]["border"],
        )
        self.options = options_config
        self.majors = options_config.get("majors", [])
        self.on_generate = on_generate
        self.on_clear = on_clear
        self.on_show_map = on_show_map
        self.conditional_answer_vars = {}
        self.major_var = tk.StringVar()
        self.education_level_var = tk.StringVar(value=options_config["education_levels"][1])
        self.current_stage_var = tk.StringVar(value=options_config["stage_options"][self.education_level_var.get()][0])
        self.major_preference_var = tk.StringVar(value=options_config["major_preference_options"][0])
        self.frontline_var = tk.StringVar(value=options_config["frontline_acceptance_options"][0])
        self._major_search_after_id = None

        self._build()
        self.education_level_var.trace_add("write", lambda *_args: self._refresh_stage_options())
        self.major_var.trace_add("write", lambda *_args: self._on_major_changed())
        self._refresh_conditional_questions()

    def _build(self):
        pad = UI_CONFIG["layout"]["padding"]
        _create_panel_heading(self, "学生画像", "填写信息，获取更精准推荐", "人").pack(anchor="w", fill="x", padx=pad, pady=(pad, 12))

        basic_card, basic_body = _create_section_card(self, "基础信息", "基")
        basic_card.pack(fill="x", padx=pad, pady=(0, 10))
        self._add_option_menu("学历层次", self.education_level_var, self.options["education_levels"], parent=basic_body)
        self._add_stage_picker(parent=basic_body)
        self._add_major_picker(parent=basic_body)

        intent_card, intent_body = _create_section_card(self, "求职意愿", "愿")
        intent_card.pack(fill="x", padx=pad, pady=(0, 10))
        self._add_option_menu("希望专业对口", self.major_preference_var, self.options["major_preference_options"], parent=intent_body)
        self._add_option_menu("接受一线场景", self.frontline_var, self.options["frontline_acceptance_options"], parent=intent_body)
        self._add_conditional_questions_area(parent=intent_body)

        self.interests = MultiSelectGroup(self, "兴趣方向（多选）", self.options["interest_options"], columns=2)
        self.interests.pack(fill="x", padx=pad, pady=(0, 10))

        self.skills = MultiSelectGroup(self, "能力资产（多选）", self.options["skill_options"], columns=2)
        self.skills.pack(fill="x", padx=pad, pady=(0, 10))

        self.avoid_tasks = MultiSelectGroup(self, "排斥项（多选）", self.options["avoid_task_options"], columns=2)
        self.avoid_tasks.pack(fill="x", padx=pad, pady=(0, 14))

        self.generate_button = ctk.CTkButton(
            self,
            text=UI_CONFIG["buttons"]["generate"],
            command=self.on_generate,
            height=40,
            font=_font("body"),
            **_button_style("primary"),
        )
        self.generate_button.pack(fill="x", padx=pad, pady=(4, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=(0, pad))
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(row, text=UI_CONFIG["buttons"]["clear"], command=self._clear, height=36, border_width=1, **_button_style("secondary")).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(row, text=UI_CONFIG["buttons"]["map"], command=self.on_show_map, height=36, border_width=1, **_button_style("success")).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _add_option_menu(self, label, variable, values, parent=None):
        pad = UI_CONFIG["layout"]["padding"]
        parent = parent or self
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=0 if parent is not self else pad, pady=(0, 10))
        ctk.CTkLabel(wrapper, text=label, font=_font("small"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", pady=(0, 6))
        BorderedArrowOptionMenu(
            wrapper,
            values=values,
            variable=variable,
            height=UI_CONFIG["dropdown"]["height"],
            font=_font("body"),
            **_option_menu_style(),
        ).pack(fill="x")

    def _add_stage_picker(self, parent=None):
        pad = UI_CONFIG["layout"]["padding"]
        parent = parent or self
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=0 if parent is not self else pad, pady=(0, 10))
        ctk.CTkLabel(wrapper, text="当前阶段", font=_font("small"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", pady=(0, 6))
        self.current_stage_menu = BorderedArrowOptionMenu(
            wrapper,
            values=self.options["stage_options"][self.education_level_var.get()],
            variable=self.current_stage_var,
            height=UI_CONFIG["dropdown"]["height"],
            font=_font("body"),
            **_option_menu_style(),
        )
        self.current_stage_menu.pack(fill="x")

    def _refresh_stage_options(self):
        if not hasattr(self, "current_stage_menu"):
            return
        values = self.options["stage_options"].get(self.education_level_var.get(), self.options["stage_options"]["其他"])
        self.current_stage_menu.configure(values=values)
        if self.current_stage_var.get() not in values:
            self.current_stage_var.set(values[0])

    def _add_major_picker(self, parent=None):
        pad = UI_CONFIG["layout"]["padding"]
        parent = parent or self
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=0 if parent is not self else pad, pady=(0, 10))
        ctk.CTkLabel(wrapper, text="专业", font=_font("small"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", pady=(0, 6))

        self.major_combo = BorderedArrowComboBox(
            wrapper,
            values=self.options["common_major_options"],
            variable=self.major_var,
            command=self._select_major,
            arrow_color=UI_CONFIG["dropdown"]["arrow_color"],
            height=UI_CONFIG["dropdown"]["height"],
            corner_radius=UI_CONFIG["dropdown"]["corner_radius"],
            border_width=UI_CONFIG["dropdown"]["border_width"],
            font=_font("body"),
            state="normal",
            fg_color=UI_CONFIG["dropdown"]["fg_color"],
            border_color=UI_CONFIG["dropdown"]["border_color"],
            button_color=UI_CONFIG["dropdown"]["button_color"],
            button_hover_color=UI_CONFIG["dropdown"]["button_hover_color"],
            text_color=UI_CONFIG["dropdown"]["text_color"],
            dropdown_fg_color=UI_CONFIG["dropdown"]["dropdown_fg_color"],
            dropdown_hover_color=UI_CONFIG["theme"]["panel_alt"],
            dropdown_text_color=UI_CONFIG["dropdown"]["dropdown_text_color"],
        )
        self.major_combo.pack(fill="x")
        self.major_combo.bind("<KeyRelease>", lambda _event: self._schedule_major_suggestions_refresh())
        self.major_combo.bind("<Return>", lambda _event: self._select_first_major_match())
        self.major_suggestions = ctk.CTkScrollableFrame(
            wrapper,
            fg_color=UI_CONFIG["theme"]["panel_alt"],
            height=132,
            corner_radius=UI_CONFIG["layout"]["card_radius"],
            border_width=UI_CONFIG["layout"]["border_width"],
            border_color=UI_CONFIG["theme"]["border"],
        )
        self.major_suggestions_open = False
        self._hide_major_suggestions()

    def _on_major_changed(self):
        self._schedule_major_suggestions_refresh()

    def _schedule_major_suggestions_refresh(self):
        if self._major_search_after_id:
            self.after_cancel(self._major_search_after_id)
        self._major_search_after_id = self.after(SEARCH_DEBOUNCE_MS, self._refresh_major_context)

    def _refresh_major_context(self):
        self._major_search_after_id = None
        self._refresh_conditional_questions()
        if hasattr(self, "major_suggestions"):
            self._refresh_major_suggestions()

    def _show_major_suggestions(self):
        if not self.major_suggestions.winfo_ismapped():
            self.major_suggestions.pack(fill="x", pady=(6, 0))
        self.major_suggestions_open = True

    def _hide_major_suggestions(self):
        if self.major_suggestions.winfo_ismapped():
            self.major_suggestions.pack_forget()
        self.major_suggestions_open = False

    def _toggle_major_suggestions(self):
        if self.major_suggestions_open:
            self._hide_major_suggestions()
            return
        self._render_major_suggestions(self._major_matches_for_current_query(show_all=True), show_title=False)

    def _refresh_major_suggestions(self, force=False):
        query = self.major_var.get().strip()
        if not query:
            self.major_combo.configure(values=self.options["common_major_options"])
            self._hide_major_suggestions()
            return
        matches = self._major_matches_for_current_query(show_all=False)
        self.major_combo.configure(values=[major["major_name"] for major in matches] or self.options["common_major_options"])
        exact_match = any(query == major["major_name"] for major in matches)
        if exact_match:
            self._hide_major_suggestions()
            return
        self._render_major_suggestions(matches, show_title=True)

    def _major_matches_for_current_query(self, show_all=False):
        query = self.major_var.get().strip()
        if query:
            return search_majors(query, self.majors, limit=12)
        common = self.options["common_major_options"]
        majors_by_name = {major["major_name"]: major for major in self.majors}
        return [majors_by_name.get(name, {"major_name": name, "major_group": ""}) for name in common]

    def _render_major_suggestions(self, matches, show_title):
        for child in self.major_suggestions.winfo_children():
            child.destroy()
        if not matches:
            self._show_major_suggestions()
            ctk.CTkLabel(
                self.major_suggestions,
                text=self.options.get("major_search_hint", "未识别到明确专业类别，将使用通用推荐逻辑"),
                text_color=UI_CONFIG["theme"]["muted"],
                font=_font("small"),
                wraplength=260,
                justify="left",
            ).pack(anchor="w")
            return
        self._show_major_suggestions()
        if show_title:
            ctk.CTkLabel(
                self.major_suggestions,
                text=f"匹配专业（{len(matches)}）",
                text_color=UI_CONFIG["theme"]["muted"],
                font=_font("small"),
            ).pack(anchor="w", pady=(0, 3))
        for major in matches:
            label = major["major_name"]
            ctk.CTkButton(
                self.major_suggestions,
                text=label,
                height=30,
                border_width=1,
                font=_font("small"),
                **_button_style("secondary"),
                command=lambda selected=major["major_name"]: self._select_major(selected),
            ).pack(fill="x", pady=2)

    def _select_first_major_match(self):
        matches = search_majors(self.major_var.get().strip(), self.majors, limit=1)
        if matches:
            self._select_major(matches[0]["major_name"])

    def _select_major(self, value):
        self.major_var.set(value)
        if hasattr(self, "major_suggestions"):
            for child in self.major_suggestions.winfo_children():
                child.destroy()
            self._hide_major_suggestions()
        if hasattr(self, "major_combo"):
            self.major_combo.configure(values=self.options["common_major_options"])

    def _add_conditional_questions_area(self, parent=None):
        pad = UI_CONFIG["layout"]["padding"]
        parent = parent or self
        self.conditional_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.conditional_frame_pad = 0 if parent is not self else pad
        self.conditional_frame_visible = False

    def _show_conditional_frame(self):
        if not self.conditional_frame_visible:
            self.conditional_frame.pack(fill="x", padx=self.conditional_frame_pad, pady=(0, 12))
            self.conditional_frame_visible = True

    def _hide_conditional_frame(self):
        if self.conditional_frame_visible:
            self.conditional_frame.pack_forget()
            self.conditional_frame_visible = False

    def _refresh_conditional_questions(self):
        if not hasattr(self, "conditional_frame"):
            return
        for child in self.conditional_frame.winfo_children():
            child.destroy()
        self.conditional_answer_vars = {}
        major = self.major_var.get().strip()
        if not major:
            self._hide_conditional_frame()
            return

        group_id = conditional_group_for_major(major, self.options, self.majors)
        groups = self.options.get("conditional_questions", {}).get("question_groups", {})
        group = groups.get(group_id)
        if not group:
            if not find_major(major, self.majors):
                self._show_conditional_frame()
                ctk.CTkLabel(
                    self.conditional_frame,
                    text=self.options.get("major_search_hint", "未识别到明确专业类别，将使用通用推荐逻辑"),
                    text_color=UI_CONFIG["theme"]["muted"],
                    font=_font("small"),
                    wraplength=260,
                    justify="left",
                ).pack(anchor="w", pady=(0, 4))
            else:
                self._hide_conditional_frame()
            return

        self._show_conditional_frame()
        ctk.CTkLabel(self.conditional_frame, text=group.get("title", "专业补充问题"), font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", pady=(0, 6))
        for question in group.get("questions", []):
            qid = question["id"]
            var = tk.StringVar(value="未选择")
            self.conditional_answer_vars[qid] = var
            ctk.CTkLabel(
                self.conditional_frame,
                text=question.get("text", ""),
                font=_font("small"),
                wraplength=260,
                justify="left",
            ).pack(anchor="w", pady=(4, 3))
            BorderedArrowOptionMenu(
                self.conditional_frame,
                values=["未选择", *question.get("options", [])],
                variable=var,
                height=32,
                font=_font("small"),
                **_option_menu_style(),
            ).pack(fill="x", pady=(0, 4))

    def set_generating(self, running):
        if hasattr(self, "generate_button"):
            self.generate_button.configure(
                state="disabled" if running else "normal",
                text="正在生成推荐..." if running else UI_CONFIG["buttons"]["generate"],
            )

    def _clear(self):
        self.major_var.set("")
        self.education_level_var.set(self.options["education_levels"][1])
        self.current_stage_var.set(self.options["stage_options"][self.education_level_var.get()][0])
        self.major_preference_var.set(self.options["major_preference_options"][0])
        self.frontline_var.set(self.options["frontline_acceptance_options"][0])
        self.interests.clear()
        self.skills.clear()
        self.avoid_tasks.clear()
        self._refresh_conditional_questions()
        self.on_clear()

    def get_profile(self):
        major = self.major_var.get().strip()
        normalized_major = normalize_major(major, self.options, self.majors)
        conditional_answers = {
            qid: var.get()
            for qid, var in self.conditional_answer_vars.items()
            if var.get() and var.get() != "未选择"
        }
        return {
            "grade": self.current_stage_var.get(),
            "education_level": self.education_level_var.get(),
            "current_stage": self.current_stage_var.get(),
            "major": major,
            "normalized_major": normalized_major,
            "major_group": normalized_major.get("major_group") or major_group_for_major(major, self.options, self.majors),
            "major_preference": self.major_preference_var.get(),
            "frontline_acceptance": self.frontline_var.get(),
            "conditional_answers": conditional_answers,
            "interests": self.interests.get_selected(),
            "skills": self.skills.get_selected(),
            "avoid_tasks": self.avoid_tasks.get_selected(),
        }


class ResultsPanel(ctk.CTkFrame):
    def __init__(self, master, jobs, on_select_job, on_export, get_profile=None):
        super().__init__(
            master,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["corner_radius"],
            border_width=UI_CONFIG["layout"]["border_width"],
            border_color=UI_CONFIG["theme"]["border"],
        )
        self.jobs = jobs
        self.on_select_job = on_select_job
        self.on_export = on_export
        self.get_profile = get_profile
        self.current_recommendations = None
        self._level_visible_counts = {}
        self._search_after_id = None
        self._pending_search_apply_id = None
        self._search_results = []
        self._search_query = ""
        self._search_visible_count = SEARCH_BATCH_SIZE
        self._is_rendering_results = False
        self._last_render_state = None
        self._build()

    def _build(self):
        pad = UI_CONFIG["layout"]["padding"]
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 8))
        header.grid_columnconfigure(0, weight=1)
        _create_panel_heading(header, "推荐结果", "根据画像生成岗位方向建议", "荐").grid(row=0, column=0, sticky="w")
        self.count_label = ctk.CTkLabel(header, text="共 0 个岗位方向", font=_font("small"), text_color=UI_CONFIG["theme"]["muted"])
        self.count_label.grid(row=0, column=1, sticky="e", padx=(8, 10))
        self.export_button = ctk.CTkButton(header, text=UI_CONFIG["buttons"]["export"], command=self.on_export, width=112, height=36, border_width=1, **_button_style("secondary"))
        self.export_button.grid(row=0, column=2, sticky="e")

        self.summary_row = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_row.grid(row=1, column=0, sticky="ew", padx=pad, pady=(0, 10))
        self.summary_row.grid_columnconfigure(4, weight=1)
        self._render_summary_counts({"优先推荐": [], "可探索": [], "暂不推荐": []})

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=2, column=0, sticky="ew", padx=pad, pady=(0, 10))
        search_row.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(search_row, placeholder_text="搜索岗位名称、类别、技能、兴趣、简历关键词", height=36, **_entry_style())
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<KeyRelease>", lambda _event: self.schedule_search_results())
        self.search_entry.bind("<Return>", lambda _event: self.show_search_results())
        self.search_button = ctk.CTkButton(search_row, text=UI_CONFIG["buttons"]["search"], command=self.show_search_results, width=86, height=36, **_button_style("primary"))
        self.search_button.grid(row=0, column=1)

        self.content = ctk.CTkScrollableFrame(self, fg_color=UI_CONFIG["theme"]["panel_alt"], corner_radius=UI_CONFIG["layout"]["corner_radius"])
        self.content.grid(row=3, column=0, sticky="nsew", padx=pad, pady=(0, pad))
        self.show_empty()

    def _render_summary_counts(self, recommendations):
        for child in self.summary_row.winfo_children():
            child.destroy()
        counts = {level: len(recommendations.get(level, [])) for level in ["优先推荐", "可探索", "暂不推荐"]}
        total = sum(counts.values())
        chips = [("全部", total, UI_CONFIG["theme"]["primary"], UI_CONFIG["theme"]["primary_soft"])]
        chips.extend((level, counts[level], _level_colors(level)["color"], _level_colors(level)["bg"]) for level in ["优先推荐", "可探索", "暂不推荐"])
        for index, (label, count, color, bg) in enumerate(chips):
            _create_badge(self.summary_row, f"{label} {count}", color=color, bg=bg).grid(row=0, column=index, sticky="w", padx=(0, 8), ipadx=9)
        _create_badge(self.summary_row, "智能排序", color=UI_CONFIG["theme"]["muted"], bg=UI_CONFIG["theme"]["panel_alt"]).grid(row=0, column=4, sticky="e", ipadx=9)
        self.count_label.configure(text=f"共 {total} 个岗位方向")

    def show_empty(self):
        self._last_render_state = None
        self._clear_content()
        self._render_summary_counts({"优先推荐": [], "可探索": [], "暂不推荐": []})
        empty = ctk.CTkFrame(self.content, fg_color=UI_CONFIG["theme"]["panel"], corner_radius=UI_CONFIG["layout"]["card_radius"], border_width=1, border_color=UI_CONFIG["theme"]["border"])
        empty.pack(fill="x", padx=12, pady=18)
        ctk.CTkLabel(empty, text="填写左侧学生画像后，点击“生成岗位方向推荐”。", text_color=UI_CONFIG["theme"]["text"], font=_font("subtitle"), justify="center").pack(padx=24, pady=(22, 6))
        ctk.CTkLabel(
            empty,
            text="系统会根据专业相关性、兴趣、能力和排斥项给出岗位方向建议。",
            text_color=UI_CONFIG["theme"]["muted"],
            font=_font("small"),
            wraplength=280,
            justify="center",
        ).pack(padx=24, pady=(0, 22))

    def show_loading(self, text="正在处理..."):
        self._clear_content()
        ctk.CTkLabel(self.content, text=text, font=_font("subtitle"), text_color=UI_CONFIG["theme"]["muted"]).pack(padx=16, pady=28)

    def set_exporting(self, running):
        if hasattr(self, "export_button"):
            self.export_button.configure(
                state="disabled" if running else "normal",
                text="正在导出..." if running else UI_CONFIG["buttons"]["export"],
            )

    def set_searching(self, running):
        if hasattr(self, "search_button"):
            self.search_button.configure(
                state="disabled" if running else "normal",
                text="搜索中..." if running else UI_CONFIG["buttons"]["search"],
            )

    def show_recommendations(self, recommendations):
        log_event("render_recommendations")
        self.current_recommendations = recommendations
        self._search_query = ""
        self._search_results = []
        self._level_visible_counts = {
            level: min(RESULT_BATCH_SIZE, len(recommendations.get(level, [])))
            for level in ["\u4f18\u5148\u63a8\u8350", "\u53ef\u63a2\u7d22", "\u6682\u4e0d\u63a8\u8350"]
        }
        self._render_recommendation_sections()

    def _result_ids_for_state(self):
        ids = []
        for level in ["\u4f18\u5148\u63a8\u8350", "\u53ef\u63a2\u7d22", "\u6682\u4e0d\u63a8\u8350"]:
            all_items = (self.current_recommendations or {}).get(level, [])
            visible_count = self._level_visible_counts.get(level, RESULT_BATCH_SIZE)
            for item in all_items[:visible_count]:
                job = item.get("job", {})
                ids.append(job.get("job_id") or job.get("job_name", ""))
        return tuple(ids)

    def _render_recommendation_sections(self):
        state = (
            "recommendations",
            tuple(sorted(self._level_visible_counts.items())),
            self._result_ids_for_state(),
        )
        if self._is_rendering_results or state == self._last_render_state:
            log_event("render_recommendations_skipped")
            return
        self._is_rendering_results = True
        self._last_render_state = state
        visible_total = len(state[2])
        log_event("render_job_cards", filter="all", count=visible_total)
        try:
            self._clear_content()
            self._render_summary_counts(self.current_recommendations or {})
            for level in ["\u4f18\u5148\u63a8\u8350", "\u53ef\u63a2\u7d22", "\u6682\u4e0d\u63a8\u8350"]:
                all_items = (self.current_recommendations or {}).get(level, [])
                visible_count = self._level_visible_counts.get(level, RESULT_BATCH_SIZE)
                self._add_level_section(level, all_items[:visible_count], total_count=len(all_items))
        finally:
            self._is_rendering_results = False

    def _load_more_level(self, level):
        if not self.current_recommendations:
            return
        total = len(self.current_recommendations.get(level, []))
        current = self._level_visible_counts.get(level, RESULT_BATCH_SIZE)
        self._level_visible_counts[level] = min(total, current + RESULT_BATCH_SIZE)
        self._render_recommendation_sections()

    def schedule_search_results(self):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(SEARCH_DEBOUNCE_MS, self.show_search_results)

    def show_search_results(self):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        if self._pending_search_apply_id:
            self.after_cancel(self._pending_search_apply_id)
            self._pending_search_apply_id = None
        self.set_searching(True)
        self._pending_search_apply_id = self.after(1, self._apply_search_results)

    def _apply_search_results(self):
        self._pending_search_apply_id = None
        log_event("after_callback", target="apply_search_results")
        try:
            query = self.search_entry.get()
            profile = self.get_profile() if self.get_profile else None
            log_event("search_jobs", query=query.strip() or "all")
            self._search_results = search_jobs(query, self.jobs, profile=profile)
            self._search_query = query
            self._search_visible_count = min(SEARCH_BATCH_SIZE, len(self._search_results))
            self._render_search_results()
        finally:
            self.set_searching(False)

    def _render_search_results(self):
        query = self._search_query
        results = self._search_results
        visible_ids = tuple((job.get("job_id") or job.get("job_name", "")) for job in results[: self._search_visible_count])
        state = ("search", query.strip(), self._search_visible_count, visible_ids)
        if self._is_rendering_results or state == self._last_render_state:
            log_event("render_job_cards_skipped", filter="search")
            return
        self._is_rendering_results = True
        self._last_render_state = state
        log_event("render_job_cards", filter="search", count=len(visible_ids))
        try:
            self._clear_content()
            title = "\u5168\u90e8\u5c97\u4f4d" if not query.strip() else f"\u641c\u7d22\u7ed3\u679c\uff1a{query}"
            self.count_label.configure(text=f"\u5171 {len(results)} \u4e2a\u5c97\u4f4d\u65b9\u5411")
            ctk.CTkLabel(self.content, text=title, font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", padx=12, pady=(12, 6))
            if not results:
                ctk.CTkLabel(self.content, text="\u6ca1\u6709\u627e\u5230\u5339\u914d\u5c97\u4f4d\uff0c\u53ef\u4ee5\u6362\u4e00\u4e2a\u5173\u952e\u8bcd\u8bd5\u8bd5\u3002", text_color=UI_CONFIG["theme"]["muted"]).pack(padx=12, pady=16)
                return
            for job in results[: self._search_visible_count]:
                self._add_job_card(job=job, score=None, level=None, reasons=[job.get("description", "")])
            if self._search_visible_count < len(results):
                remaining = len(results) - self._search_visible_count
                ctk.CTkButton(
                    self.content,
                    text=f"\u52a0\u8f7d\u66f4\u591a\uff08\u5269\u4f59 {remaining} \u4e2a\uff09",
                    command=self._load_more_search_results,
                    height=34,
                    border_width=1,
                    **_button_style("secondary"),
                ).pack(fill="x", padx=10, pady=(4, 12))
        finally:
            self._is_rendering_results = False

    def _load_more_search_results(self):
        self._search_visible_count = min(len(self._search_results), self._search_visible_count + SEARCH_BATCH_SIZE)
        self._render_search_results()

    def _add_level_section(self, level, items, total_count=None):
        colors = _level_colors(level)
        section_header = ctk.CTkFrame(self.content, fg_color="transparent")
        section_header.pack(fill="x", padx=12, pady=(16, 6))
        section_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(section_header, text=colors["display"], font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"]).grid(row=0, column=0, sticky="w")
        total = len(items) if total_count is None else total_count
        badge_text = f"{len(items)}/{total} \u4e2a\u65b9\u5411" if total > len(items) else f"{total} \u4e2a\u65b9\u5411"
        _create_badge(section_header, badge_text, color=colors["color"], bg=colors["bg"]).grid(row=0, column=1, sticky="e", ipadx=8)
        if not items:
            ctk.CTkLabel(self.content, text="暂无该层级岗位。", text_color=UI_CONFIG["theme"]["muted"]).pack(anchor="w", padx=12, pady=(0, 8))
            return
        for item in items:
            self._add_job_card(
                job=item["job"],
                score=item["score"],
                level=item["level"],
                reasons=item["reasons"],
                result=item,
            )
        if total_count and len(items) < total_count:
            remaining = total_count - len(items)
            ctk.CTkButton(
                self.content,
                text=f"加载更多{colors['display']}（剩余 {remaining} 个）",
                command=lambda level=level: self._load_more_level(level),
                height=34,
                border_width=1,
                **_button_style("secondary"),
            ).pack(fill="x", padx=10, pady=(2, 10))

    def _add_job_card(self, job, score, level, reasons, result=None):
        level_style = _level_colors(level)
        relevance = job.get("major_relevance", "低专业限制")
        relevance_style = _relevance_colors(relevance)
        card = ctk.CTkFrame(
            self.content,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["card_radius"],
            border_width=1,
            border_color=level_style.get("border", UI_CONFIG["theme"]["border"]),
        )
        card.pack(fill="x", padx=10, pady=6)
        card.grid_columnconfigure(0, weight=1)
        display_name = _job_display_name(job)
        title_label = ctk.CTkLabel(card, text=display_name, font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"], anchor="w", justify="left", wraplength=260)
        title_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
        _bind_wrap(title_label, min_width=180, horizontal_padding=10)
        if score is not None:
            score_frame = ctk.CTkFrame(card, fg_color="transparent")
            score_frame.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(0, 12), pady=(10, 0))
            ctk.CTkLabel(score_frame, text=str(score), font=_font("score"), text_color=UI_CONFIG["theme"]["text"]).pack(side="left")
            ctk.CTkLabel(score_frame, text="分", font=_font("small"), text_color=UI_CONFIG["theme"]["muted"]).pack(side="left", padx=(2, 0), pady=(6, 0))
        if level:
            _create_badge(card, text=level, color=level_style["color"], bg=level_style["bg"]).grid(row=2, column=1, sticky="e", padx=(0, 12), pady=(0, 8), ipadx=8)
        meta_row = ctk.CTkFrame(card, fg_color="transparent")
        meta_row.grid(row=1, column=0, sticky="w", padx=14, pady=(2, 6))
        _create_badge(meta_row, relevance, color=relevance_style["color"], bg=relevance_style["bg"], font_key="tiny", height=22).pack(side="left", padx=(0, 6), ipadx=7)
        _create_badge(meta_row, job["category"], color=UI_CONFIG["theme"]["muted"], bg=UI_CONFIG["theme"]["panel_alt"], font_key="tiny", height=22).pack(side="left", padx=(0, 6), ipadx=7)
        summary = reasons[0] if reasons else job.get("description", "")
        summary_label = ctk.CTkLabel(card, text=summary, wraplength=260, justify="left", font=_font("small"), text_color=UI_CONFIG["theme"]["muted"], anchor="w")
        summary_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        _bind_wrap(summary_label, min_width=180, horizontal_padding=10)
        ctk.CTkButton(card, text="查看详情  →", width=96, height=30, font=_font("small"), command=lambda: self.on_select_job(job, result), border_width=1, **_button_style("secondary")).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()


class JobDetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(
            master,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["corner_radius"],
            border_width=UI_CONFIG["layout"]["border_width"],
            border_color=UI_CONFIG["theme"]["border"],
        )
        self._is_rendering_detail = False
        self._last_rendered_job_id = None
        self._last_detail_signature = None
        self.show_placeholder()

    def _detail_label(self, text, font_key="body", text_color=None, pady=(0, 2), master=None):
        master = master or self
        label = ctk.CTkLabel(
            master,
            text=text,
            text_color=text_color or UI_CONFIG["theme"]["text"],
            wraplength=self._wraplength(),
            justify="left",
            font=_font(font_key),
            anchor="w",
        )
        label.pack(anchor="w", fill="x", padx=14, pady=pady)
        return label

    def _wraplength(self):
        width = self.winfo_width()
        if width <= 80:
            return 300
        return max(220, width - 34)

    def show_placeholder(self):
        self._last_rendered_job_id = None
        self._last_detail_signature = None
        self._clear()
        _create_panel_heading(self, "岗位详情", "点击中间岗位卡片查看完整分析", "析").pack(anchor="w", fill="x", padx=16, pady=(16, 12))
        empty = ctk.CTkFrame(self, fg_color=UI_CONFIG["theme"]["panel_alt"], corner_radius=UI_CONFIG["layout"]["card_radius"], border_width=1, border_color=UI_CONFIG["theme"]["border"])
        empty.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(empty, text="点击中间的岗位卡片后，这里会显示完整岗位分析。", text_color=UI_CONFIG["theme"]["muted"], font=_font("body"), wraplength=280, justify="center").pack(padx=20, pady=24)

    def show_job(self, job, result=None):
        job_id = job.get("job_id") or job.get("job_name", "")
        signature = (job_id, result.get("score") if result else None, result.get("level") if result else None)
        if self._is_rendering_detail or signature == self._last_detail_signature:
            log_event("render_job_detail_skipped", job_id=job_id)
            return
        self._is_rendering_detail = True
        self._last_rendered_job_id = job_id
        self._last_detail_signature = signature
        log_event("render_job_detail", job_id=job_id)
        try:
            self._clear()
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=16, pady=(16, 10))
            header.grid_columnconfigure(0, weight=1)
            title_label = ctk.CTkLabel(header, text=_job_display_name(job), font=_font("title"), text_color=UI_CONFIG["theme"]["text"], anchor="w", justify="left", wraplength=260)
            title_label.grid(row=0, column=0, sticky="ew")
            _bind_wrap(title_label, min_width=220, horizontal_padding=8)
            if result:
                score_box = ctk.CTkFrame(header, fg_color=UI_CONFIG["theme"]["primary_soft"], corner_radius=12)
                score_box.grid(row=0, column=1, sticky="ne", padx=(10, 0))
                ctk.CTkLabel(score_box, text=str(result["score"]), font=_font("panel_title"), text_color=UI_CONFIG["theme"]["primary"]).pack(side="left", padx=(10, 2), pady=5)
                ctk.CTkLabel(score_box, text="分", font=_font("small"), text_color=UI_CONFIG["theme"]["primary"]).pack(side="left", padx=(0, 10), pady=(8, 5))
            sub = f"{job['category']} · 难度 {job['difficulty']} · 成长价值 {job['growth_value']}"
            sub_label = ctk.CTkLabel(header, text=sub, font=_font("small"), text_color=UI_CONFIG["theme"]["muted"], anchor="w", justify="left", wraplength=260)
            sub_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
            _bind_wrap(sub_label, min_width=220, horizontal_padding=8)
            badge_row = ctk.CTkFrame(self, fg_color="transparent")
            badge_row.pack(fill="x", padx=16, pady=(0, 10))
            relevance = job.get("major_relevance", "低专业限制")
            relevance_style = _relevance_colors(relevance)
            _create_badge(badge_row, relevance, color=relevance_style["color"], bg=relevance_style["bg"]).pack(side="left", padx=(0, 6), ipadx=8)
            if result:
                colors = _level_colors(result["level"])
                _create_badge(badge_row, result["level"], color=colors["color"], bg=colors["bg"]).pack(side="left", padx=(0, 6), ipadx=8)
                self._section("岗位概览", [job["description"]])
                self._section("推荐理由", result["reasons"])
                major_items = [job.get("major_relevance", "")]
                major_items.extend(job.get("suitable_majors", [])[:8])
                self._section("专业匹配", major_items, tags=True)
                self._section("能力匹配", result.get("matched_skills", []) or ["暂无明显匹配能力"], tags=True)
                self._section("需要补充的能力", result.get("missing_skills", []) or ["暂无明显短板"], tags=True)
                if result.get("avoid_hits"):
                    self._section("命中的排斥项", result["avoid_hits"], tags=True)
            else:
                self._section("岗位概览", [job["description"]])
            if job.get("display_name") and job.get("display_name") != job.get("job_name"):
                self._section("原始岗位方向", [job.get("job_name", "")])
            self._section("岗位是干什么的", [job["description"]])
            self._section("日常工作内容", job.get("daily_tasks", []))
            self._section("岗位要求能力", job.get("required_skills", []), tags=True)
            self._section("准备建议", [job.get("preparation_advice", "")])
            self._section("简历关键词", job.get("resume_keywords", []), tags=True)
            if job.get("posting_aliases"):
                self._section("真实招聘中可能出现的名称", job.get("posting_aliases", []), tags=True)
            self._section("适合专业", job.get("suitable_majors", []), tags=True)
            self._section("专业限制程度", [job.get("major_relevance", "")], tags=True)
            self._section("可能不适合的人群", job.get("not_suitable_for", []))

        finally:
            self._is_rendering_detail = False

    def _section(self, title, values, tags=False):
        section = ctk.CTkFrame(
            self,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["card_radius"],
            border_width=1,
            border_color=UI_CONFIG["theme"]["border"],
        )
        section.pack(fill="x", padx=14, pady=(0, 8))
        self._detail_label(title, font_key="subtitle", pady=(12, 6), master=section)
        items = [item for item in values if item]
        if tags and items:
            _tag_row(section, items).pack(anchor="w", fill="x", padx=14, pady=(0, 8))
            return
        if not items:
            self._detail_label("无", text_color=UI_CONFIG["theme"]["muted"], pady=(0, 12), master=section)
            return
        for item in items:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(anchor="w", fill="x", padx=14, pady=(0, 6))
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row,
                text="\u2022",
                width=12,
                font=_font("body"),
                text_color=UI_CONFIG["theme"]["text"],
                anchor="n",
            ).grid(row=0, column=0, sticky="n", padx=(0, 5), pady=(1, 0))
            ctk.CTkLabel(
                row,
                text=str(item),
                wraplength=260,
                justify="left",
                font=_font("body"),
                text_color=UI_CONFIG["theme"]["text"],
                anchor="w",
            ).grid(row=0, column=1, sticky="ew")
        ctk.CTkFrame(section, fg_color="transparent", height=6).pack(fill="x")

    def _clear(self):
        for child in self.winfo_children():
            child.destroy()


class JobMapWindow(ctk.CTkToplevel):
    def __init__(self, master, jobs, on_select_job):
        super().__init__(master)
        self.jobs = jobs
        self.on_select_job = on_select_job
        self.title("全部岗位地图")
        self.geometry("900x680")
        self.minsize(720, 520)
        self.configure(fg_color=UI_CONFIG["theme"]["bg"])
        self._search_after_id = None
        self._jobs_for_display = []
        self._visible_count = JOB_MAP_BATCH_SIZE
        self._build()
        self.transient(master)
        self.focus()

    def _apply_responsive_geometry(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(900, int(screen_width * 0.82))
        height = min(680, int(screen_height * 0.82))
        min_width = min(720, max(620, int(screen_width * 0.72)))
        min_height = min(520, max(460, int(screen_height * 0.72)))
        width = max(min_width, width)
        height = max(min_height, height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min_width, min_height)
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        top.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(top, placeholder_text="搜索岗位地图", height=36, **_entry_style())
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<KeyRelease>", lambda _event: self.schedule_render())
        self.search_entry.bind("<Return>", lambda _event: self.render())
        ctk.CTkButton(top, text="??", command=self.render, width=90, height=36, **_button_style("primary")).grid(row=0, column=1)
        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color=UI_CONFIG["theme"]["panel"],
            corner_radius=UI_CONFIG["layout"]["corner_radius"],
            border_width=UI_CONFIG["layout"]["border_width"],
            border_color=UI_CONFIG["theme"]["border"],
        )
        self.content.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.render()

    def schedule_render(self):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(SEARCH_DEBOUNCE_MS, self.render)

    def render(self):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        self._jobs_for_display = search_jobs(self.search_entry.get(), self.jobs)
        self._visible_count = min(JOB_MAP_BATCH_SIZE, len(self._jobs_for_display))
        self._render_visible_jobs()

    def _render_visible_jobs(self):
        for child in self.content.winfo_children():
            child.destroy()
        jobs = self._jobs_for_display[: self._visible_count]
        if not jobs:
            ctk.CTkLabel(self.content, text="没有找到匹配岗位。", text_color=UI_CONFIG["theme"]["muted"]).pack(pady=24)
            return
        for category, items in group_jobs_by_category(jobs).items():
            ctk.CTkLabel(self.content, text=f"{category}（{len(items)}）", font=_font("subtitle"), text_color=UI_CONFIG["theme"]["text"]).pack(anchor="w", padx=12, pady=(14, 6))
            row = ctk.CTkFrame(self.content, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(0, 8))
            for index, job in enumerate(items):
                button = ctk.CTkButton(row, text=_job_display_name(job), width=150, height=32, command=lambda selected=job: self._select(selected), **_button_style("secondary"), border_width=1)
                button.grid(row=index // 4, column=index % 4, sticky="ew", padx=4, pady=4)
        if self._visible_count < len(self._jobs_for_display):
            remaining = len(self._jobs_for_display) - self._visible_count
            ctk.CTkButton(
                self.content,
                text=f"加载更多岗位（剩余 {remaining} 个）",
                command=self._load_more_jobs,
                height=34,
                border_width=1,
                **_button_style("secondary"),
            ).pack(fill="x", padx=12, pady=(6, 14))

    def _load_more_jobs(self):
        self._visible_count = min(len(self._jobs_for_display), self._visible_count + JOB_MAP_BATCH_SIZE)
        self._render_visible_jobs()

    def _select(self, job):
        self.on_select_job(job, None)


class InternCompassApp(ctk.CTk):
    def __init__(self, jobs, options_config, rules_config):
        super().__init__()
        self.jobs = jobs
        self.options_config = options_config
        self.rules_config = rules_config
        self.current_profile = None
        self.current_recommendations = None
        self.clicked_jobs = []
        self.current_run = None
        self.job_result_index = {}
        self.current_selected_job_key = None
        self._is_generating = False
        self._is_exporting = False
        self._setup_window()
        self._build_layout()

    def _setup_window(self):
        ctk.set_appearance_mode(UI_CONFIG["theme"]["appearance_mode"])
        ctk.set_default_color_theme(UI_CONFIG["theme"]["color_theme"])
        self.title(UI_CONFIG["window"]["title"])
        self.configure(fg_color=UI_CONFIG["theme"]["bg"])
        self._apply_responsive_window()

    @staticmethod
    def _calculate_window_geometry(screen_width, screen_height):
        window = UI_CONFIG["window"]
        width = min(window["width"], int(screen_width * window.get("max_screen_width_ratio", 0.9)))
        height = min(window["height"], int(screen_height * window.get("max_screen_height_ratio", 0.88)))
        min_width = min(window["min_width"], max(820, int(screen_width * window.get("min_screen_width_ratio", 0.96))))
        min_height = min(window["min_height"], max(500, int(screen_height * window.get("min_screen_height_ratio", 0.94))))
        width = max(min_width, width)
        height = max(min_height, height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        return width, height, min_width, min_height, x, y

    def _apply_responsive_window(self):
        width, height, min_width, min_height, x, y = self._calculate_window_geometry(
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min_width, min_height)

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=28, minsize=240)
        self.grid_columnconfigure(1, weight=34, minsize=280)
        self.grid_columnconfigure(2, weight=38, minsize=300)
        self.grid_rowconfigure(1, weight=1)

        title_bar = ctk.CTkFrame(self, fg_color="transparent")
        title_bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=18, pady=(14, 10))
        title_bar.grid_columnconfigure(1, weight=1)
        logo = ctk.CTkLabel(
            title_bar,
            text="IC",
            width=42,
            height=42,
            fg_color=UI_CONFIG["theme"]["primary"],
            text_color="#FFFFFF",
            corner_radius=21,
            font=_font("panel_title"),
        )
        logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        ctk.CTkLabel(title_bar, text=UI_CONFIG["window"]["product_name"], font=_font("title"), text_color=UI_CONFIG["theme"]["text"]).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title_bar, text=UI_CONFIG["window"]["subtitle"], font=_font("small"), text_color=UI_CONFIG["theme"]["muted"]).grid(row=1, column=1, sticky="w", pady=(2, 0))
        _create_badge(title_bar, UI_CONFIG["window"]["version"], color=UI_CONFIG["theme"]["primary"], bg=UI_CONFIG["theme"]["primary_soft"]).grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 8), ipadx=10)
        status = ctk.CTkFrame(title_bar, fg_color="transparent")
        status.grid(row=0, column=3, rowspan=2, sticky="e")
        ctk.CTkLabel(status, text="●", font=_font("small"), text_color=UI_CONFIG["levels"]["优先推荐"]["color"]).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(status, text=UI_CONFIG["window"]["runtime"], font=_font("small"), text_color=UI_CONFIG["theme"]["text"]).pack(side="left")

        self.form = StudentProfileForm(self, self.options_config, self.generate, self.clear_results, self.show_job_map)
        self.form.grid(row=1, column=0, sticky="nsew", padx=(18, 6), pady=(0, 18))

        self.results_panel = ResultsPanel(self, self.jobs, self.select_job, self.export_current_report, get_profile=self.form.get_profile)
        self.results_panel.grid(row=1, column=1, sticky="nsew", padx=6, pady=(0, 18))

        self.detail_panel = JobDetailPanel(self)
        self.detail_panel.grid(row=1, column=2, sticky="nsew", padx=(6, 18), pady=(0, 18))

    def generate(self):
        log_event("on_generate_click")
        if self._is_generating:
            log_event("on_generate_click_ignored", reason="is_generating")
            return
        profile = self.form.get_profile()
        if not profile["major"]:
            messagebox.showwarning("需要补充信息", "请先填写或选择专业。")
            return
        if not profile["interests"] and not profile["skills"]:
            messagebox.showwarning("需要补充信息", "请至少选择一个喜欢的工作内容或当前能力。")
            return
        if profile.get("major_group") == "通用类" and not find_major(profile["major"], self.options_config.get("majors", [])):
            messagebox.showinfo("专业识别提示", self.options_config.get("major_search_hint", "未识别到明确专业类别，将使用通用推荐逻辑"))

        self.current_profile = profile
        self.clicked_jobs = []
        self.current_recommendations = None
        self.current_run = None
        self.job_result_index = {}
        self.current_selected_job_key = None
        self._is_generating = True
        self.form.set_generating(True)
        self.results_panel.show_loading("正在生成推荐...")

        def worker():
            try:
                log_event("generate_recommendations")
                recommendations = calculate_recommendations(profile, self.jobs, self.options_config, self.rules_config)
                run_record = save_user_run(profile, recommendations, clicked_jobs=[])
            except Exception as exc:
                self.after(0, lambda exc=exc: self._finish_generate_error(exc))
                return
            self.after(0, lambda: self._finish_generate_success(recommendations, run_record))

        _run_daemon(worker)

    def _finish_generate_success(self, recommendations, run_record):
        log_event("after_callback", target="finish_generate_success")
        self._is_generating = False
        self.form.set_generating(False)
        self.current_recommendations = recommendations
        self.current_run = run_record
        self.job_result_index = {
            item["job"].get("job_name", ""): item
            for item in recommendations.get("all", [])
        }
        self.results_panel.show_recommendations(recommendations)
        first = recommendations.get("优先推荐", []) or recommendations.get("可探索", [])
        if first:
            self.select_job(first[0]["job"], first[0])

    def _finish_generate_error(self, error):
        self._is_generating = False
        self.form.set_generating(False)
        log_file = _write_error_log(error)
        suffix = f"\n\n错误日志：{log_file}" if log_file else ""
        messagebox.showerror("生成失败", f"生成推荐时遇到问题，请稍后重试。{suffix}")

    def select_job(self, job, result=None):
        job_name = job.get("job_name", "")
        job_id = job.get("job_id") or job_name
        if result is None and self.current_recommendations:
            result = self.job_result_index.get(job_name)
        selected_key = (job.get("job_id") or job_name, result.get("score") if result else None)
        if selected_key == self.current_selected_job_key:
            log_event("render_job_detail_skipped", job_id=job_id)
            return
        self.current_selected_job_key = selected_key
        if job_name and job_name not in self.clicked_jobs:
            self.clicked_jobs.append(job_name)
        self.detail_panel.show_job(job, result)

    def clear_results(self):
        self.current_profile = None
        self.current_recommendations = None
        self.clicked_jobs = []
        self.current_run = None
        self.job_result_index = {}
        self.current_selected_job_key = None
        self.results_panel.show_empty()
        self.detail_panel.show_placeholder()

    def export_current_report(self):
        if self._is_exporting:
            return
        if not self.current_profile or not self.current_recommendations:
            messagebox.showinfo("暂无推荐报告", "请先生成岗位方向推荐，再导出报告。")
            return
        self._is_exporting = True
        self.results_panel.set_exporting(True)

        profile = self.current_profile
        recommendations = self.current_recommendations

        def worker():
            try:
                output = export_report(profile, recommendations)
            except Exception as exc:
                self.after(0, lambda exc=exc: self._finish_export_error(exc))
                return
            self.after(0, lambda: self._finish_export_success(output))

        _run_daemon(worker)

    def _finish_export_success(self, output):
        self._is_exporting = False
        self.results_panel.set_exporting(False)
        if isinstance(output, dict):
            message = "推荐报告已生成：\n" + "\n".join(str(path) for path in output.values())
        else:
            message = f"推荐报告已生成：\n{output}"
        messagebox.showinfo("导出成功", message)

    def _finish_export_error(self, error):
        self._is_exporting = False
        self.results_panel.set_exporting(False)
        log_file = _write_error_log(error)
        suffix = f"\n\n错误日志：{log_file}" if log_file else ""
        messagebox.showerror("导出失败", f"导出推荐报告时遇到问题。{suffix}")

    def show_job_map(self):
        JobMapWindow(self, self.jobs, self.select_job)


def _font(size_key):
    config = UI_CONFIG["font"]
    return (config["family"], config[size_key])
