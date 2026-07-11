APP_BG = "#F6F8FB"
CARD_BG = "#FFFFFF"
CARD_ALT_BG = "#F8FAFC"
CARD_SOFT_BG = "#F9FBFF"
PRIMARY_COLOR = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_SOFT = "#EFF6FF"
TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#64748B"
TEXT_TERTIARY = "#94A3B8"
BORDER_COLOR = "#E2E8F0"
BORDER_STRONG = "#CBD5E1"
DROPDOWN_BORDER_COLOR = "#CBD5E1"
DROPDOWN_ARROW_COLOR = "#1E3A8A"

SUCCESS_BG = "#DCFCE7"
SUCCESS_TEXT = "#047857"
SUCCESS_BORDER = "#BBF7D0"
WARNING_BG = "#FEF3C7"
WARNING_TEXT = "#B45309"
WARNING_BORDER = "#FED7AA"
DANGER_BG = "#FEE2E2"
DANGER_TEXT = "#DC2626"
DANGER_BORDER = "#FECACA"
INFO_BG = "#DBEAFE"
INFO_TEXT = "#1D4ED8"
INFO_BORDER = "#BFDBFE"
NEUTRAL_BG = "#F1F5F9"
NEUTRAL_TEXT = "#475569"
NEUTRAL_BORDER = "#E2E8F0"
TAG_BG = "#EEF2FF"
TAG_TEXT = "#3154D4"

CARD_RADIUS = 12
BUTTON_RADIUS = 9
INPUT_RADIUS = 8

PADDING_XS = 6
PADDING_SM = 8
PADDING_MD = 12
PADDING_LG = 18
PADDING_XL = 24

DROPDOWN_STYLE = {
    "fg_color": CARD_BG,
    "border_color": DROPDOWN_BORDER_COLOR,
    "border_width": 1,
    "button_color": CARD_BG,
    "button_hover_color": PRIMARY_SOFT,
    "dropdown_fg_color": CARD_BG,
    "dropdown_text_color": TEXT_PRIMARY,
    "text_color": TEXT_PRIMARY,
    "arrow_color": DROPDOWN_ARROW_COLOR,
    "corner_radius": INPUT_RADIUS,
}


UI_CONFIG = {
    "window": {
        "title": "Intern Compass 大学生实习方向推荐工具",
        "product_name": "Intern Compass",
        "subtitle": "大学生实习方向推荐工具 · 内测版",
        "version": "v1.0",
        "runtime": "本地运行",
        "width": 1280,
        "height": 820,
        "min_width": 1080,
        "min_height": 660,
        "max_screen_width_ratio": 0.9,
        "max_screen_height_ratio": 0.88,
        "min_screen_width_ratio": 0.96,
        "min_screen_height_ratio": 0.94,
    },
    "theme": {
        "appearance_mode": "light",
        "color_theme": "blue",
        "bg": APP_BG,
        "panel": CARD_BG,
        "panel_alt": CARD_ALT_BG,
        "panel_soft": CARD_SOFT_BG,
        "primary": PRIMARY_COLOR,
        "primary_hover": PRIMARY_HOVER,
        "primary_soft": PRIMARY_SOFT,
        "text": TEXT_PRIMARY,
        "muted": TEXT_SECONDARY,
        "subtle": TEXT_TERTIARY,
        "border": BORDER_COLOR,
        "border_strong": BORDER_STRONG,
        "tag_bg": TAG_BG,
        "tag_text": TAG_TEXT,
    },
    "dropdown": {
        **DROPDOWN_STYLE,
        "button_width": 34,
        "height": 36,
        "entry_fg": CARD_BG,
    },
    "font": {
        "family": "Microsoft YaHei UI",
        "title": 22,
        "panel_title": 17,
        "subtitle": 14,
        "body": 13,
        "small": 12,
        "tiny": 11,
        "score": 24,
    },
    "layout": {
        "corner_radius": CARD_RADIUS,
        "card_radius": CARD_RADIUS,
        "button_radius": BUTTON_RADIUS,
        "input_radius": INPUT_RADIUS,
        "padding": PADDING_LG,
        "padding_xs": PADDING_XS,
        "padding_sm": PADDING_SM,
        "padding_md": PADDING_MD,
        "padding_lg": PADDING_LG,
        "padding_xl": PADDING_XL,
        "gap": PADDING_MD,
        "border_width": 1,
    },
    "buttons": {
        "generate": "生成岗位方向推荐",
        "clear": "清空表单",
        "export": "导出推荐报告",
        "map": "查看全部岗位地图",
        "search": "搜索岗位",
    },
    "levels": {
        "优先推荐": {
            "display": "优先推荐",
            "color": SUCCESS_TEXT,
            "bg": SUCCESS_BG,
            "border": SUCCESS_BORDER,
        },
        "可探索": {
            "display": "可探索",
            "color": WARNING_TEXT,
            "bg": WARNING_BG,
            "border": WARNING_BORDER,
        },
        "暂不推荐": {
            "display": "暂不推荐",
            "color": DANGER_TEXT,
            "bg": DANGER_BG,
            "border": DANGER_BORDER,
        },
    },
    "relevance": {
        "强专业对口": {"color": INFO_TEXT, "bg": INFO_BG, "border": INFO_BORDER},
        "强专业相关": {"color": INFO_TEXT, "bg": INFO_BG, "border": INFO_BORDER},
        "弱专业相关": {"color": WARNING_TEXT, "bg": "#FFF7ED", "border": WARNING_BORDER},
        "低专业限制": {"color": NEUTRAL_TEXT, "bg": NEUTRAL_BG, "border": NEUTRAL_BORDER},
        "默认": {"color": TAG_TEXT, "bg": TAG_BG, "border": INFO_BORDER},
    },
    "buttons_style": {
        "primary": {"fg_color": PRIMARY_COLOR, "hover_color": PRIMARY_HOVER, "text_color": "#FFFFFF"},
        "secondary": {"fg_color": CARD_BG, "hover_color": CARD_ALT_BG, "text_color": TEXT_PRIMARY, "border_color": BORDER_COLOR},
        "ghost": {"fg_color": CARD_ALT_BG, "hover_color": "#EEF2F7", "text_color": TEXT_SECONDARY, "border_color": BORDER_COLOR},
        "success": {"fg_color": "#ECFDF3", "hover_color": SUCCESS_BG, "text_color": SUCCESS_TEXT, "border_color": SUCCESS_BORDER},
    },
}
