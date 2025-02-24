from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

root_dir = Path(__file__).parent.parent.parent

data_dir = root_dir.joinpath("data")
icon_dir = data_dir.joinpath("icons")

TOOLBAR_ICON_SIZE = QSize(20, 20)


def label_and_widget(label_text: str, widget: QWidget, *widgets: QWidget, add_stretch=True, tooltip="") -> QHBoxLayout:
    label = QLabel(label_text)

    if tooltip:
        label.setToolTip(tooltip)

    layout = QHBoxLayout()

    layout.addWidget(label)

    if add_stretch:
        layout.addStretch(1)

    layout.addWidget(widget)

    for additional_widget in widgets:
        layout.addWidget(additional_widget)

    return layout


def ctrl_is_pressed():
    return bool(QApplication.keyboardModifiers() & Qt.ControlModifier)


@lru_cache(256)
def icon(icon_name: str):
    icon_path = icon_dir / icon_name
    data_path = data_dir / icon_name

    if icon_path.exists():
        return QIcon(str(icon_path))
    elif data_path.exists():
        return QIcon(str(data_path))
    else:
        raise FileNotFoundError(icon_path)


def is_generic_directive(line: str):
    if not line:
        return False

    directive = line.split()[0]

    return directive.upper() in DIRECTIVES


def is_instruction(line: str):
    line = strip_comment(line)

    instruction, *_ = line.split(" ")

    return instruction in INSTRUCTIONS


def strip_comment(line: str):
    semi_colon_index = line.find(";")

    if semi_colon_index == -1:
        return line.strip()

    return line[:semi_colon_index].strip()


DIRECTIVES = [
    ".LIST",
    ".NOLIST",
    ".MLIST",
    ".NOMLIST",
    ".OPT",
    ".EQU",
    ".BANK",
    ".ORG",
    ".DB",
    ".DW",
    ".BYTE",
    ".WORD",
    ".DS",
    ".RSSET",
    ".RS",
    ".MACRO",
    ".ENDM",
    ".PROC",
    ".ENDP",
    ".PROCGROUP",
    ".ENDPROCGROUP",
    ".INCBIN",
    ".INCLUDE",
    ".INCCHR",
    ".DEFCHR",
    ".ZP",
    ".BSS",
    ".CODE",
    ".DATA",
    ".IF",
    ".IFDEF",
    ".IFNDEF",
    ".ELSE",
    ".ENDIF",
    ".FAIL",
    ".INESPRG",
    ".INESCHR",
    ".INESMAP",
    ".INESMIR",
]

INSTRUCTIONS = [
    "ADC",
    "AND",
    "ASL",
    "BCC",
    "BCS",
    "BEQ",
    "BIT",
    "BMI",
    "BNE",
    "BPL",
    "BRA",
    "BRK",
    "BVC",
    "BVS",
    "CLC",
    "CLD",
    "CLI",
    "CLV",
    "CMP",
    "CPX",
    "CPY",
    "DEC",
    "DEX",
    "DEY",
    "EOR",
    "INC",
    "INX",
    "INY",
    "JMP",
    "JSR",
    "LDA",
    "LDX",
    "LDY",
    "LSR",
    "NOP",
    "ORA",
    "PHA",
    "PHP",
    "PLA",
    "PLP",
    "ROL",
    "ROR",
    "RTI",
    "RTS",
    "SBC",
    "SEC",
    "SED",
    "SEI",
    "STA",
    "STX",
    "STY",
    "TAX",
    "TAY",
    "TSX",
    "TXA",
    "TXS",
    "TYA",
]
