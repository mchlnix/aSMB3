from dataclasses import dataclass
from math import ceil, log
from pathlib import Path


@dataclass
class AsmPosition:
    file: Path
    line_no: int
    size: int


def strip_comment(line: str):
    semi_colon_index = line.find(";")

    if semi_colon_index == -1:
        return line.strip()

    return line[:semi_colon_index].strip()


def byte_length_of_number_string(value):
    value = value.removeprefix("-")

    if value.startswith("%"):
        return len(value.removeprefix("%")) // 8

    elif value.startswith("$"):
        return len(value.removeprefix("$")) // 2

    elif value.startswith("'"):
        assert value.count("'") == 2
        return len(value) - 2

    elif value.isnumeric():
        return ceil(log(1 + value, 256))

    else:
        raise ValueError(f"Unexpected {value}")


OPERATORS = "+,-,*,/,%,^,&,|,~,<<,>>".split(",")


COMPARATORS = "=,!=,!,<,>,<=,>=".split(",")
BUILT_IN_FUNCTIONS = ["HIGH", "LOW", "BANK", "PAGE", "SIZEOF"]


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

FUNCTIONS = ["HIGH", "LOW", "BANK", "PAGE", "SIZEOF"]

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

RELATIVE_ADDRESSING_INSTRUCTIONS = [
    "BCC",
    "BCS",
    "BEQ",
    "BMI",
    "BNE",
    "BPL",
    "BRA",
    "BVC",
    "BVS",
]
