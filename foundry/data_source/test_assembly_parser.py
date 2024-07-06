from pathlib import Path

import pytest

from foundry.data_source import AsmPosition
from foundry.data_source.assembly_parser import AssemblyParser
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


def test_ines_header():
    ap = AssemblyParser(Path())

    ap._ines_mapper = 5
    ap._ines_mirror = 6

    assert ap.ines_header[6] == 0x56

    assert ap.ines_header[7] == 0


def test_line_from_position():
    expected_line = ".word Level_SlopeQuad00	; Tile quad $00"

    path_to_prg = Path("/home/michael/Gits/smb3/PRG/prg000.asm")

    line = AssemblyParser._line_from_position(AsmPosition(path_to_prg, 29, 0))

    assert line == expected_line


def test_convert_line_to_bytes():
    expected_bytes = b"\x08\xC0"

    ap = AssemblyParser(Path())
    ap._symbol_lut["Level_SlopeQuad00"] = AsmPosition(Path(), 29, 0xC008)

    assert expected_bytes == ap._convert_line_to_bytes(".word Level_SlopeQuad00")
