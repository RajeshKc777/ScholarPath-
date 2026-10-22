"""Visual tokens and the application stylesheet.

Reddit-style light look (reference: user-shared mock, 2026-10-20): white
chrome with orange accents, light-blue assistant bubbles, orange user
bubbles. Widgets must not hardcode hex values that are not local accents -
shared colour lives here.
"""

from __future__ import annotations

# Reddit-style light palette.
# Orange accents on white; assistant bubbles stay light blue.
PALETTE: dict[str, str] = {
    "page": "#FBFCFE",
    "surface": "#FFFFFF",
    "border": "#E8ECF2",
    "border_strong": "#DCE2EB",
    "text": "#17202E",
    "text_secondary": "#56657D",
    "text_muted": "#8E9AB0",
    "orange": "#FF4500",
    "orange_soft": "#FF7A45",
    "orange_deep": "#E8481A",
    "blue": "#3B82F6",
    "cyan": "#0891B2",
    "mint": "#10B981",
    "amber": "#B45309",
    "pink": "#DB2777",
    "danger": "#BE123C",
    "tint_orange": "#FFF4EC",
    "border_orange": "#FFDEC8",
    "tint_green": "#EAF9F0",
    "tint_blue": "#EAF2FF",
}

FONT_UI = "'Segoe UI'"
FONT_MONO = "'Consolas'"
FONT_ICON = "'Segoe MDL2 Assets'"

GRADIENT_BLUE = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #FF7A45, stop:1 #E8481A)"
)
GRADIENT_USER = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #FF8A50, stop:1 #EF5B1E)"
)
GRADIENT_HERO = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
    "stop:0 #FFF2E7, stop:0.55 #FFF7F1, stop:1 #FFFBF7)"
)
GRADIENT_NAVY_CARD = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
    "stop:0 #FFF2E7, stop:1 #FFFBF7)"
)
GRADIENT_SEND = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
    "stop:0 #FF8A50, stop:1 #EA5514)"
)


def stylesheet() -> str:
    p = PALETTE
    return f"""
QWidget {{
    color: {p['text']};
    font-family: {FONT_UI};
    font-size: 13px;
}}
QWidget#Root {{ background: {p['page']}; }}
QMainWindow {{ background: {p['page']}; }}

/* Scroll areas paint the page colour themselves. The scroll area frame, the
   viewport Qt creates inside it, and the widget set as its content are all
   plain QWidgets; without a rule they fall back to the system palette, which
   is near-black when Windows is in dark mode. One rule here covers every
   page, the right-hand panel and the eligibility dialog. */
QScrollArea {{
    background: {p['page']};
    border: none;
}}
QScrollArea > QWidget#qt_scrollarea_viewport {{
    background: {p['page']};
}}
QScrollArea > QWidget > QWidget {{
    background: {p['page']};
}}

/* ---------------- sidebar ---------------- */
QWidget#Sidebar {{
    background: {p['surface']};
    border-right: 1px solid {p['border']};
}}
QLabel#BrandName {{ color: {p['text']}; font-size: 17px; font-weight: 700; }}
QLabel#BrandTag {{ color: {p['text_muted']}; font-size: 10px; }}
QLabel#RailSection {{
    color: #A2ACBE;
    font-size: 10px;
    letter-spacing: 1.6px;
    font-weight: 700;
}}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 12px;
    text-align: left;
}}
QPushButton#NavButton:hover {{ background: rgba(0, 0, 0, 0.045); }}
QPushButton#NavButton[active="true"] {{ background: {GRADIENT_BLUE}; }}
QPushButton#NavButton:disabled {{ background: transparent; }}
QLabel#NavText {{ color: {p['text_secondary']}; font-size: 12px; background: transparent; }}
QLabel#NavTextActive {{
    color: #FFFFFF; font-size: 12px; font-weight: 600; background: transparent;
}}
QLabel#NavIcon {{ color: #9AA6BC; background: transparent; }}
QLabel#NavIconActive {{ color: #FFFFFF; background: transparent; }}
QLabel#NavBadge {{
    color: #9AA6BC;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 7px;
    padding: 1px 6px;
    font-size: 9px;
}}
QFrame#SidebarCard {{
    background: {GRADIENT_NAVY_CARD};
    border-radius: 16px;
    border: 1px solid {p['border_orange']};
}}
QLabel#SidebarCardTitle {{ color: {p['text']}; font-size: 13px; font-weight: 700; }}
QLabel#SidebarCardBody {{ color: {p['text_secondary']}; font-size: 10px; }}

/* ---------------- top bar ---------------- */
QWidget#TopBar {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}
QLabel#PageTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#PageSub {{ color: {p['text_muted']}; font-size: 11px; }}
QLabel#StatusPill {{
    color: #C2410C;
    background: {p['tint_orange']};
    border: 1px solid {p['border_orange']};
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
}}
QToolButton#VoiceModeButton {{
    color: {p['text_secondary']};
    background: {p['surface']};
    border: 1px solid {p['border_strong']};
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QToolButton#VoiceModeButton:hover {{
    color: {p['orange_deep']};
    border-color: {p['border_orange']};
}}
QToolButton#VoiceModeButton:checked {{
    color: {p['orange_deep']};
    background: {p['tint_orange']};
    border-color: {p['border_orange']};
}}
QToolButton#VoiceModeButton:disabled {{
    color: #A5AEBC;
    background: #F5F6F8;
    border-color: #E5E7EB;
}}
QLabel#StatusLive {{
    color: #15803D;
    background: transparent;
    border: none;
    padding: 0px 2px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#Avatar {{
    background: {GRADIENT_SEND};
    color: #FFFFFF;
    border-radius: 17px;
    font-weight: 700;
    font-size: 14px;
}}

/* ---------------- conversation ---------------- */
QScrollArea#Transcript, QWidget#TranscriptBody {{
    background: {p['page']};
    border: none;
}}
QFrame#HeroCard {{
    background: {GRADIENT_HERO};
    border: 1px solid #FFE3D3;
    border-radius: 18px;
}}
QLabel#HeroTitle {{ font-size: 22px; font-weight: 700; color: {p['text']}; }}
QLabel#HeroSub {{ color: #7C665A; font-size: 12px; }}
QLabel#HeroAvatar {{
    background: {GRADIENT_SEND};
    color: #FFFFFF;
    border-radius: 26px;
    font-size: 22px;
}}

QPushButton#ActionTile {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 14px;
    text-align: left;
}}
QPushButton#ActionTile:hover {{ border: 1px solid #FFC6A8; background: #FFF9F6; }}
QPushButton#ActionTile:pressed {{ background: {p['tint_orange']}; }}
QLabel#TileTitle {{ font-size: 11px; font-weight: 600; color: {p['text']}; }}
QLabel#TileSub {{ font-size: 9px; color: {p['text_muted']}; }}
QLabel#TileBadge {{
    color: #7B8798;
    background: #F5F6F8;
    border-radius: 7px;
    padding: 1px 5px;
    font-size: 8px;
}}

QFrame#AsstBubble {{
    background: #EAF2FF;
    border: 1px solid #D6E4FF;
    border-radius: 14px;
}}
QFrame#UserBubble {{
    background: {GRADIENT_USER};
    border: none;
    border-radius: 14px;
}}
QLabel#AsstLabel {{
    color: #9AA8BE;
    font-size: 10px;
    letter-spacing: 1.2px;
    font-weight: 700;
}}
QLabel#UserLabel {{
    color: #FFE3D1;
    font-size: 9px;
    letter-spacing: 1.2px;
    font-weight: 700;
}}
QLabel#AsstBody {{ color: #1F2A3C; font-size: 13px; }}
QLabel#UserBody {{ color: #FFFFFF; font-size: 13px; }}
QLabel#TurnAvatar {{
    background: {GRADIENT_SEND};
    color: #FFFFFF;
    border-radius: 14px;
    font-size: 12px;
}}
QFrame#ErrorBlock {{
    background: #FFF1F4;
    border: 1px solid #FBD0DA;
    border-radius: 12px;
}}
QLabel#ErrLabel {{
    color: {p['danger']};
    font-size: 10px;
    letter-spacing: 1.2px;
    font-weight: 700;
}}
QLabel#ErrBody {{ color: #9F1239; font-size: 12.5px; }}
QToolButton#Copy {{
    color: {p['text_muted']};
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 11px;
}}
QToolButton#Copy:hover {{ color: {p['orange_deep']}; background: {p['tint_orange']}; }}

/* ---------------- right panel ---------------- */
QScrollArea#RightScroll, QWidget#RightBody,
QScrollArea#DocScroll, QWidget#DocBody,
QScrollArea#ProfileScroll {{
    background: {p['page']};
    border: none;
}}
QFrame#PanelCard {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 16px;
}}
QFrame#PrivacyRow {{
    background: transparent;
    border: none;
    border-top: 1px solid {p['border']};
}}
QLabel#CardTitle {{ font-size: 13px; font-weight: 700; color: {p['text']}; }}
QLabel#CardLink {{ color: {p['orange_deep']}; font-size: 11px; font-weight: 600; }}
QLabel#ProfileName {{ font-size: 14px; font-weight: 700; }}
QLabel#ProfileSub {{ color: {p['text_muted']}; font-size: 10px; }}
QFrame#Track {{ background: #E7EAF0; border-radius: 3px; }}
QLabel#TrackLabel {{ color: {p['text_muted']}; font-size: 9.5px; }}
QLabel#RowLabel {{ color: {p['text_muted']}; font-size: 9.5px; }}
QLabel#RowValue {{ color: {p['text']}; font-size: 12px; font-weight: 600; }}
QLabel#MiniIcon {{
    background: {p['tint_blue']};
    color: {p['blue']};
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
}}
QFrame#InfoCard {{
    background: {p['tint_orange']};
    border: 1px solid {p['border_orange']};
    border-radius: 12px;
}}
QLabel#InfoText {{ color: #9A4A22; font-size: 10px; }}
QLabel#CapName {{ color: {p['text_secondary']}; font-size: 11px; }}
QLabel#CapLive {{
    color: #15803D;
    background: {p['tint_green']};
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#CapSoon {{
    color: {p['text_muted']};
    background: #F5F6F8;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
}}
QLabel#CapFail {{
    color: #B91C1C;
    background: #FEE2E2;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#CapAmber {{
    color: #B45309;
    background: #FEF3C7;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#CapGrey {{
    color: #475569;
    background: #EEF1F5;
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#StateWhy {{
    color: {p['text_secondary']};
    font-size: 11px;
    background: transparent;
}}
QLabel#StateWhat {{
    color: {p['text_muted']};
    font-size: 10px;
    background: transparent;
}}
QPushButton#LinkButton {{
    color: {p['orange']};
    background: transparent;
    border: none;
    font-size: 11px;
    text-align: left;
    padding: 0;
}}
QPushButton#LinkButton:hover {{ text-decoration: underline; }}

/* ---------------- composer ---------------- */
QFrame#Composer {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 16px;
}}
QFrame#Composer[focused="true"] {{ border: 1px solid #FFC6A8; }}
QPlainTextEdit#Input {{
    background: transparent;
    border: none;
    color: {p['text']};
    font-size: 13px;
    padding: 11px 2px 0 2px;
    selection-background-color: #FFE3D5;
    selection-color: {p['text']};
}}
QToolButton#Attach {{
    color: {p['text_muted']};
    background: transparent;
    border: none;
    border-radius: 9px;
    font-size: 15px;
}}
QToolButton#Attach:hover {{ color: {p['orange']}; background: {p['tint_orange']}; }}
QPushButton#Send {{
    background: {GRADIENT_SEND};
    color: #FFFFFF;
    border: none;
    border-radius: 20px;
}}
QPushButton#Send:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF7A3D, stop:1 #E03F0C);
}}
QPushButton#Send:disabled {{ background: #DBD5D0; }}
QLabel#Hint {{ color: #A5AEBC; font-size: 10px; }}
/* ---------------- live voice bar ---------------- */
QFrame#VoiceBar {{
    background: {p['tint_orange']};
    border: 1px solid {p['border_orange']};
    border-radius: 12px;
}}
QLabel#VoiceState {{ color: {p['orange_deep']}; font-size: 12px; font-weight: 700; }}
QLabel#VoiceDetail {{ color: {p['text_secondary']}; font-size: 10px; }}
QToolButton#VoiceEnd {{
    color: {p['orange_deep']};
    background: {p['surface']};
    border: 1px solid {p['border_orange']};
    border-radius: 12px;
    padding: 4px 14px;
    font-size: 11px;
    font-weight: 700;
}}
QToolButton#VoiceEnd:hover {{ background: {p['border_orange']}; }}
/* ---------------- status strip ---------------- */
QWidget#StatusStrip {{ background: {p['surface']}; border-top: 1px solid {p['border']}; }}
QLabel#Status {{ color: {p['text_muted']}; font-size: 10px; }}
QLabel#StatusWarn {{ color: #C2410C; font-size: 10px; }}
QLabel#StatusErr {{ color: {p['danger']}; font-size: 10px; }}
QLabel#StatusPath {{
    color: #A5AEBC;
    font-family: {FONT_MONO};
    font-size: 9px;
}}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 3px 1px; }}
QScrollBar::handle:vertical {{
    background: #D3DAE5; border-radius: 3px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #B6C0CE; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

/* ---------------- profile & documents pages ---------------- */
QLabel#PageTitle2 {{
    color: {p['text']};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#PageLead {{ color: {p['text_muted']}; font-size: 12px; }}
QLabel#FieldLabel {{ color: {p['text_muted']}; font-size: 10px; }}
QLineEdit#PField, QComboBox#PCombo {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 9px;
    padding: 7px 10px;
    font-size: 12px;
    color: {p['text']};
}}
QLineEdit#PField:focus, QComboBox#PCombo:focus {{ border: 1px solid #FFC6A8; }}
QLineEdit#PField:disabled {{
    background: #F4F1EE;
    color: #A5AEBC;
}}
QComboBox#PCombo::drop-down {{ border: none; width: 18px; }}
QComboBox#PCombo::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p['text_muted']};
}}
QComboBox QAbstractItemView {{
    background: {p['surface']};
    color: {p['text']};
    selection-background-color: {p['tint_orange']};
    selection-color: {p['text']};
    border: 1px solid {p['border_strong']};
}}
QPushButton#PrimaryButton {{
    background: {GRADIENT_SEND};
    color: #FFFFFF;
    border: none;
    border-radius: 11px;
    padding: 9px 20px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF7A3D, stop:1 #E03F0C);
}}
QPushButton#PrimaryButton:disabled {{ background: #DBD5D0; color: #FFFFFF; }}
QPushButton#GhostButton {{
    background: {p['tint_orange']};
    color: {p['orange']};
    border: 1px solid {p['border_orange']};
    border-radius: 11px;
    padding: 9px 18px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#GhostButton:hover {{ background: #FFE3D4; }}
QPushButton#GhostButton:disabled {{ color: #A5AEBC; border-color: {p['border']}; }}
QLabel#VerifyOK {{ color: #15803D; font-size: 10px; }}
QLabel#VerifyWarn {{ color: #C2410C; font-size: 10px; }}
QLabel#VerifySkip {{ color: {p['text_muted']}; font-size: 10px; }}
QFrame#DocCard {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 12px;
}}
QLabel#DocName {{ color: {p['text']}; font-size: 12px; font-weight: 600; }}
QLabel#DocMeta {{ color: {p['text_muted']}; font-size: 10px; }}
QPlainTextEdit#SourcePreview {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    font-family: {FONT_MONO};
    font-size: 10px;
    color: {p['text']};
}}

QToolTip {{
    background: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    padding: 5px 8px;
    font-size: 11px;
}}
"""
