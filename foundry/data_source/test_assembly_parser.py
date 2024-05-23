from pathlib import Path

import pytest

from foundry.data_source import AsmPosition
from foundry.data_source.macro import Macro


@pytest.fixture
def macro_example():
    macro_example = [
        "MusSeg .macro",
        ".byte \\1	; Music_RestH_Base value (always divisible by $10; base part of index into PRG031's Music_RestH...",
        ".word \\2	; Address of music segment data (all tracks this segment, offsets to follow, except implied Squ...",
        ".byte \\3	; Triangle track starting offset ($00 means disabled)",
        ".byte \\4	; Square 1 track starting offset (cannot be disabled)",
        ".byte \\5	; Noise track starting offset ($00 means disabled)",
        ".byte \\6	; DCM track starting offset ($00 means disabled)",
        ".endm",
    ]

    return macro_example


@pytest.fixture
def asm_position():
    return AsmPosition(Path(), 0, 0)


@pytest.fixture
def macro(macro_example, asm_position):
    return Macro.parse_macro(macro_example, asm_position)


def test_macro_lines(macro):
    assert macro.lines == [
        "MusSeg .macro",
        ".byte \\1",
        ".word \\2",
        ".byte \\3",
        ".byte \\4",
        ".byte \\5",
        ".byte \\6",
        ".endm",
    ]


def test_macro_expansion(macro):
    args = ["$FF", "$FFFF", "$FF", "Bro_Const", "$FF", "$FF"]

    expanded_macro = macro.expand(*args)

    assert expanded_macro == [
        "MusSeg .macro",
        ".byte $FF",
        ".word $FFFF",
        ".byte $FF",
        ".byte Bro_Const",
        ".byte $FF",
        ".byte $FF",
        ".endm",
    ]
