import os
from collections import OrderedDict
from pathlib import Path

from foundry.data_source import (
    BYTE_DIRECTIVE,
    COMPARATORS,
    DIRECTIVES,
    FUNCTIONS,
    INSTRUCTIONS,
    OPERATORS,
    RELATIVE_ADDRESSING_INSTRUCTIONS,
    WORD_DIRECTIVE,
    AsmPosition,
    strip_comment,
)
from foundry.data_source.formula_parser import FormulaParser, LeafType
from foundry.data_source.macro import Macro
from smb3parse.util import apply, bin_int, hex_int

os.chdir("/home/michael/Gits/smb3")

smb3_asm_file = Path("smb3.asm")

assert smb3_asm_file.exists()

BYTES_PER_WORD = 2


def _is_only_comment(line: str):
    return bool(line and not strip_comment(line))


def _is_empty_line(line: str):
    return not line.strip()


def _is_ignored_directive(line: str):
    if not _is_generic_directive(line):
        return False

    directive = strip_comment(line).split(" ")[0]
    return directive in [".data", ".org", ".code"]


def _is_generic_directive(line: str):
    directive = line.split()[0]

    return directive.upper() in DIRECTIVES


def _is_ds_directive(line: str):
    if ".ds" not in line:
        return False

    if line.strip().startswith(".ds"):
        return True

    # space before a directive is not necessary
    line = line.replace(".ds", " .ds")

    name, ds, value = strip_comment(line).split()
    return ds == ".ds"


def _is_func_directive(line: str):
    if ".func" not in line:
        return False

    parts = line.split(".func")

    return len(parts) == 2


def _is_ines_directive(line: str):
    line = strip_comment(line)

    if not line.startswith(".ines"):
        return False

    parts = line.split(" ")

    return len(parts) == 2


def _is_include_directive(line: str):
    line = strip_comment(line)

    return ".include" in line


def _is_symbol_definition(line: str):
    line = strip_comment(line)

    if ":" not in line:
        return len(line.split()) == 1

    return not line.startswith(":")  # have some name before the colon


def _is_const_assignment(line: str):
    parts = strip_comment(line).split("=")

    return len(parts) == 2


def _is_byte(line: str):
    # TODO count the bytes
    return BYTE_DIRECTIVE in line or ".db" in line


def _is_word(line: str):
    # TODO count the words
    return WORD_DIRECTIVE in line or ".dw" in line


def _is_instruction(line: str):
    line = strip_comment(line)

    instruction, *_ = line.split(" ")

    return instruction in INSTRUCTIONS


def _parse_number(number_str: str):
    number_str = number_str.strip()

    # hexadecimal ($7F), binary (%0101) and decimal (48). Character values are also supported ('A')
    if number_str.startswith("-"):
        number_str = number_str[1:]
        is_negative = True
    else:
        is_negative = False

    if number_str.startswith("$"):
        # hexadecimal
        number = hex_int(number_str[1:])

        assert 0x0 <= number <= 0xFFFF

    elif number_str.startswith("%"):
        number = bin_int(number_str[1:])

        assert 0b0000_0000 <= number <= 0b1111_1111

    elif number_str.startswith("'"):
        number_str = number_str.replace("'", "")
        assert len(number_str) == 1

        number = ord(number_str)

        assert ord("A") <= number <= ord("Z")

    elif number_str.isnumeric():
        number = int(number_str)

    else:
        raise ValueError(f"Couldn't parse number '{number_str}'.")

    if is_negative:
        number = -number

    return number


def _split_byte_word_parts(line):
    line = strip_comment(line)

    if line.startswith((BYTE_DIRECTIVE, WORD_DIRECTIVE)):
        symbol = None
        definition = line

    else:
        if BYTE_DIRECTIVE in line:
            search_for = BYTE_DIRECTIVE
        elif WORD_DIRECTIVE in line:
            search_for = WORD_DIRECTIVE
        else:
            raise ValueError("What?")

        symbol, definition = line.split(search_for)
        symbol = symbol.replace(":", "").strip()

    fp = FormulaParser(definition)
    fp.parse()

    return fp.parts


def _is_calculation(line: str):
    if line.startswith(("-", "%", "$")):
        line = line[1:]  # discard sign or number format character from the start

    if any(operator in line for operator in OPERATORS):
        return True

    if any(comparator in line for comparator in COMPARATORS):
        return True

    return False


def _parse_calculation(line: str):
    for operator in OPERATORS:
        if operator in line[1:]:
            left, right = map(str.strip, line.split(operator))

            break
    else:
        raise ValueError(f"Couldn't parse calculation {line}")

    return left, right, operator


class AssemblyParser:
    def __init__(self, path_to_assembly: Path):
        self._root_dir = path_to_assembly

        self._macro_lut: dict[str, Macro] = {}
        self._const_lut: dict[str, str] = {}
        self._func_lut: dict[str, AsmPosition] = {}
        self._incl_lut: dict[str, int] = {}
        self._ram_lut: dict[str, AsmPosition] = {}
        self._symbol_lut: dict[str, AsmPosition] = {}

        self._prg_lut: dict[int, Path] = {}
        self._chr_lut: list[str] = []

        self._pos_to_asm_lut: OrderedDict[float, AsmPosition] = OrderedDict()
        """
        A dictionary connecting the positions in the assembled ROM with their code counterparts. Not every position is
        represented, so find the closest without going over and reparse the piece of code to find the exact match.
        """

        self._current_byte_offset: int = 0
        """Running count of the byte position in the ROM we currently are, when parsing the assembly code."""

        self._line_co = 0
        """The current line we are at, in the file we are currently parsing."""

        self._prg_count = 0
        """Number of PRG banks this assembly purports to have."""

        self._chr_count = 0
        """Number of CHR banks this assembly purports to have."""

        # TODO: shared byte with mirror. do special handling when reading and writing to this position (6)
        self._ines_mapper = 0

        self._ines_mirror = 0

    def parse(self):
        self._parse_smb3_asm()

        self._current_byte_offset = 0x10  # after the INES header

        for prg_file in self._prg_lut.values():
            if not prg_file.is_file():
                raise ValueError(f"Could not load {prg_file} correctly. Doesn't exist or is not a file.")

            self._prg_pass_1(prg_file)

        for prg_file in self._prg_lut.values():
            if not prg_file.is_file():
                raise ValueError(f"Could not load {prg_file} correctly. Doesn't exist or is not a file.")

            self._prg_pass_2(prg_file)

            assert self._current_byte_offset == 0x2000, (prg_file, hex(0x2000 - self._current_byte_offset))

    def _parse_smb3_asm(self):
        self._line_co = 0

        smb3_asm = self._root_dir / "smb3.asm"

        if not smb3_asm.is_file():
            raise ValueError(f"Could not load {smb3_asm} correctly. Doesn't exist or is not a file.")

        with smb3_asm.open() as f:
            lines = f.readlines()

        line_count = len(lines)

        while lines:
            line = lines[0].replace("\t", " ")
            self._line_co += 1

            if _is_empty_line(line):
                # no byte size
                self._print_line("Empty Line", lines.pop(0).strip())

            elif _is_only_comment(line):
                # no byte size
                self._print_line("Comment", lines.pop(0).strip())

            elif _is_ds_directive(line):
                # no byte size
                self._print_line("Directive ds", lines.pop(0).strip())

                ram_var = strip_comment(line).split(".ds")[0].replace(":", "").strip()

                self._ram_lut[ram_var] = AsmPosition(smb3_asm, self._line_co)

            elif _is_func_directive(line):
                line = strip_comment(line)

                func_name = line.split(" ")[0].strip().replace(":", "")

                self._func_lut[func_name] = AsmPosition(smb3_asm_file, self._line_co)

                self._print_line("Directive func", lines.pop(0).strip())

            elif _is_ines_directive(line):
                self._handle_ines_directive(lines, smb3_asm)

            elif _is_byte(line):
                if line.startswith(BYTE_DIRECTIVE):
                    continue

                symbol_name = line.split(BYTE_DIRECTIVE)[0].replace(":", "").strip()

                self._symbol_lut[symbol_name] = AsmPosition(smb3_asm_file, self._line_co)

            elif _is_word(line):
                if line.startswith(WORD_DIRECTIVE):
                    continue

                symbol_name = line.split(WORD_DIRECTIVE)[0].replace(":", "").strip()

                self._symbol_lut[symbol_name] = AsmPosition(smb3_asm_file, self._line_co)

            elif self._try_bank_directive(lines):
                pass

            elif self._try_incchr_directive(lines):
                pass

            elif _is_ignored_directive(line):
                self._print_line("Directive igno", lines.pop(0).strip())

            elif Macro.macro_on_line(line):
                macro = Macro.parse_macro(lines, AsmPosition(smb3_asm_file, self._line_co))

                self._macro_lut[macro.name] = macro

                for line in macro.lines:
                    lines.pop(0)
                    self._print_line("Macro", line)
                    self._line_co += 1

                self._line_co -= 1

                continue

            elif _is_generic_directive(line):
                self._print_line("Directive", lines.pop(0).strip())
                raise ValueError("Unhandled Directive")

            elif _is_const_assignment(line):
                line = strip_comment(line)

                self._print_line("Const Assign", lines.pop(0).strip())

                name, value = map(str.strip, line.split("="))

                if name in self._const_lut:
                    raise ValueError(f"Redefinition of {name}")

                elif _is_calculation(value):
                    left, right, operator = _parse_calculation(value)
                    print(left, right, operator)

                    value = "xx"

                self._const_lut[name] = value

            elif _is_symbol_definition(line):
                self._print_line("Symbol Define", lines.pop(0).strip())

                symbol = strip_comment(line).split(":")[0].strip()

                self._symbol_lut[symbol] = AsmPosition(smb3_asm, self._line_co)

            else:
                self._print_line("Ignoring", lines.pop(0).strip())
                raise ValueError("What was that?")

        assert line_count == self._line_co

    def _handle_ines_directive(self, lines, smb3_asm):
        line = strip_comment(lines[0])
        ines_directive, value = line.split()
        if ines_directive == ".inesprg":
            self._prg_count = int(value)

            self._pos_to_asm_lut[4] = AsmPosition(smb3_asm, self._line_co)

        elif ines_directive == ".ineschr":
            self._chr_count = int(value)

            self._pos_to_asm_lut[5] = AsmPosition(smb3_asm, self._line_co)

        # TODO support extended mappers in byte 7
        elif ines_directive == ".inesmap":
            self._ines_mapper = int(value)

            self._pos_to_asm_lut[6] = AsmPosition(smb3_asm, self._line_co)

        elif ines_directive == ".inesmir":
            self._ines_mirror = int(value)

            self._pos_to_asm_lut[6.5] = AsmPosition(smb3_asm, self._line_co)

        self._print_line("Directive ines", lines.pop(0).strip())

    def _prg_pass_1(
        self,
        prg_file: Path,
    ):
        print(f"Pass 1 of {prg_file}")
        self._line_co = 0

        with prg_file.open() as f:
            lines = f.readlines()

        line_count = len(lines)

        while lines:
            line = lines[0].replace("\t", " ")
            self._line_co += 1

            if _is_empty_line(line):
                # no byte size
                pass

            elif _is_only_comment(line):
                # no byte size
                pass

            elif _is_func_directive(line):
                line = strip_comment(line)

                func_name = line.split(" ")[0].strip().replace(":", "")
                print(func_name)

                self._func_lut[func_name] = AsmPosition(prg_file, self._line_co)

            elif _is_ds_directive(line):
                # no byte size
                self._print_line("Directive ds", line)

                ram_var = strip_comment(line).split(".ds")[0].replace(":", "").strip()

                self._ram_lut[ram_var] = AsmPosition(prg_file, self._line_co)

            elif _is_byte(line):
                line = strip_comment(line)

                if not line.startswith(BYTE_DIRECTIVE):
                    symbol_name = line.split(BYTE_DIRECTIVE)[0].replace(":", "").strip()

                    self._symbol_lut[symbol_name] = AsmPosition(smb3_asm_file, self._line_co)

            elif _is_word(line):
                line = strip_comment(line)

                if not line.startswith(WORD_DIRECTIVE):
                    symbol_name = line.split(WORD_DIRECTIVE)[0].replace(":", "").strip()

                    self._symbol_lut[symbol_name] = AsmPosition(smb3_asm_file, self._line_co)

            elif Macro.macro_on_line(line):
                macro = Macro.parse_macro(lines, AsmPosition(prg_file, self._line_co))

                self._macro_lut[macro.name] = macro

                for line in macro.lines:
                    lines.pop(0)
                    self._line_co += 1

                    self._print_line("Macro", line)

                self._line_co -= 1

                continue

            elif _is_include_directive(line):
                self._print_line("Directive Incl", line)

                line = strip_comment(line)

                if ":" in line:
                    # read any data includes, like levels in step 2
                    lines.pop(0)
                    continue

                file_name = line.split(".include")[1].replace('"', "").strip()
                absolute_name = self._root_dir / file_name

                if not absolute_name.is_file():
                    # TODO make error message
                    absolute_name = absolute_name.with_suffix(".asm")

                line_count_before = self._line_co
                self._prg_pass_1(absolute_name)

                self._line_co = line_count_before

            elif _is_symbol_definition(line):
                self._print_line("Symbol Define", strip_comment(line))

                symbol = strip_comment(line).split(":")[0].strip()

                self._symbol_lut[symbol] = AsmPosition(prg_file, self._line_co)

            elif _is_const_assignment(line):
                line = strip_comment(line)

                self._print_line("Const Assign", line)

                name, value = map(str.strip, line.split("="))

                if value in self._const_lut:
                    raise ValueError(f"Redefinition of {name}")

                elif self._is_func_call(value):
                    # todo, eval the function
                    value_int = "func"

                elif _is_calculation(value):
                    left, right, operator = _parse_calculation(value)
                    # todo, eval the operation
                    value_int = "calc"
                    print(left, right, operator)

                else:
                    value_int = _parse_number(value)

                self._const_lut[name] = value_int

            else:
                self._print_line("Ignoring", line.strip())

            lines.pop(0)

        assert line_count == self._line_co, (line_count, self._line_co)

    def _prg_pass_2(self, prg_file):
        print(f"Pass 2 of {prg_file}")
        self._line_co = 0
        self._current_byte_offset = 0

        with prg_file.open() as f:
            lines = f.readlines()

        line_count = len(lines)

        while lines:
            line = lines[0].replace("\t", " ").strip()

            self._line_co += 1

            if _is_empty_line(line):
                # no byte size
                self._print_line("Empty Line", lines.pop(0).strip())

            elif _is_only_comment(line):
                # no byte size
                self._print_line("Comment", lines.pop(0).strip())

            elif _is_byte(line):
                self._print_line("Byte Include  ", lines.pop(0).strip())

                word_co = self._count_bytes_or_words(line)

                self._current_byte_offset += word_co

            elif _is_word(line):
                self._print_line("Word Include  ", lines.pop(0).strip())

                word_co = self._count_bytes_or_words(line)

                self._current_byte_offset += word_co

            elif _is_ignored_directive(line):
                self._print_line("Directive igno", lines.pop(0).strip())

            elif _is_func_directive(line):
                line = strip_comment(line)

                func_name = line.split(" ")[0].strip()

                self._func_lut[func_name] = AsmPosition(smb3_asm_file, self._line_co)

                self._print_line("Directive func", lines.pop(0).strip())

            elif _is_instruction(line):
                self._print_line("Instruction", lines.pop(0).strip())

                byte_co = self._count_instruction(line)

                self._current_byte_offset += byte_co

            elif Macro.macro_on_line(line):
                self._print_line("Macro Start", lines.pop(0).strip())

                while ".endm" not in lines[0]:
                    self._line_co += 1
                    self._print_line("Macro Define", lines.pop(0).strip())

                self._line_co += 1
                self._print_line("Macro End", lines.pop(0).strip())

            elif macro_name := self._is_macro_invoke(line):
                self._print_line("Macro Invoke", lines.pop(0).strip())

                self._count_macro(line, macro_name)

            elif self._is_func_call(line):
                self._print_line("Func Invoke", lines.pop(0).strip())

            elif _is_const_assignment(line):
                self._print_line("Const Assign", lines.pop(0).strip())

            elif _is_include_directive(line):
                self._print_line("Directive Incl", lines.pop(0).strip())

                symbol, path = map(str.strip, strip_comment(line).split(".include"))
                symbol = symbol.strip().removesuffix(":")
                self._symbol_lut[symbol] = AsmPosition(prg_file, self._line_co)

                path = path.replace('"', "").strip()

                if not path.endswith(".asm"):
                    path += ".asm"

                assert (self._root_dir / path).is_file(), self._root_dir / path

                self._current_byte_offset += self._count_include_bytes(self._root_dir / path)

            elif _is_symbol_definition(line):
                self._print_line("Symbol Define", lines.pop(0).strip())

                parts = apply(str.strip, strip_comment(line).split(":"))

                # symbols can have instructions following them
                if len(parts) > 1 and _is_instruction(parts[1]):
                    byte_co = self._count_instruction(parts[1])

                    self._current_byte_offset += byte_co

            else:
                self._print_line("Ignoring", lines.pop(0).strip())

                if strip_comment(line) != "org $D800":  # known bad line. ignore
                    raise ValueError(f"What was that? PRG {prg_file.name}")

        assert line_count == self._line_co, (line_count, self._line_co, prg_file)

    def _count_include_bytes(self, path: Path):
        with path.open() as f:
            lines = filter(lambda line: _is_byte(line) or _is_word(line), f.readlines())

        return sum(self._count_bytes_or_words(line) for line in lines)

    def _count_macro(self, line, macro_name):
        macro = self._macro_lut[macro_name]
        assert line.startswith(macro_name), (line, macro_name)

        args = line.replace(f"{macro_name} ", "").split(",")

        _start, *expanded_lines, _end = macro.expand(*args)

        for expanded_line in expanded_lines:
            self._print_line("Macro Expand", expanded_line)

            if inner_macro_name := self._is_macro_invoke(expanded_line):
                self._count_macro(expanded_line, inner_macro_name)

                continue

            elif _is_byte(expanded_line):
                word_co = self._count_bytes_or_words(expanded_line)

                self._current_byte_offset += word_co

            elif _is_word(expanded_line):
                word_co = self._count_bytes_or_words(expanded_line)

                self._current_byte_offset += word_co * BYTES_PER_WORD

            else:
                self._current_byte_offset += self._count_instruction(expanded_line)

    def _is_macro_invoke(self, line):
        if ".macro" in line:
            return ""

        line = strip_comment(line).split(" ")

        if line[0] in self._macro_lut:
            return line[0]
        else:
            return ""

    def _count_bytes_or_words(self, line):
        if BYTE_DIRECTIVE in line:
            return self._count_occurrences(line, BYTE_DIRECTIVE)

        if WORD_DIRECTIVE in line:
            return self._count_occurrences(line, WORD_DIRECTIVE)

        raise ValueError(f"Bruh, What? {line}")

    @staticmethod
    def _count_occurrences(line: str, delimiter: str):
        if delimiter == BYTE_DIRECTIVE:
            occurrence_value = 1
        elif delimiter == WORD_DIRECTIVE:
            occurrence_value = 2
        else:
            raise ValueError(f"Bruh, What? {line}")

        parts = strip_comment(line).split(delimiter)

        _symbol, definition = parts

        definition = definition.strip()

        if definition[0] == '"' == definition[-1] == '"':
            print("Found String")
            return len(definition) - 2

        fp = FormulaParser(definition)
        fp.parse()

        assert len(fp.tree.leaves) == 1

        if fp.tree.leaves[0].leaf_type == LeafType.LISTING:
            leaf_count = len(fp.tree.leaves[0].leaves)

            return leaf_count * occurrence_value

        else:
            return occurrence_value

    def _num_or_const(self, line: str):
        line = line.strip()

        if line in self._const_lut:
            return self._const_lut[line]

        return _parse_number(line)

    def _count_instruction(self, line: str):
        line = strip_comment(line)

        if line.endswith(" A"):
            # explicit address of accumulator
            return 1

        if " " in line:
            opcode, args = line.split(" ", maxsplit=1)
        else:
            opcode, args = line, ""

        assert opcode.upper() in INSTRUCTIONS

        if not args:
            return 1

        if opcode.upper() in RELATIVE_ADDRESSING_INSTRUCTIONS:
            return 2

        if opcode.upper() == "JMP":
            return 3

        return self._count_instruction_args(args)

    def _count_instruction_args(self, args: str):
        args = args.replace(" ", "")

        if args.startswith("#"):
            # direct addressing
            return 2

        if args.startswith(("<", "[")):
            # zero page addressing
            return 2

        args = args.replace(",X", "").replace(",Y", "")

        fp = FormulaParser(args)
        fp.parse()

        print(fp.parts)

        if any(part in self._ram_lut for part in fp.parts):
            return 3
        if any(part in self._symbol_lut or part in self._const_lut for part in fp.parts):
            return 3

        if self._num_or_const(args) > 0xFF:
            return 3
        else:
            return 2

    def _is_func_call(self, line: str):
        line = strip_comment(line)

        if "(" not in line or ")" not in line:
            return False

        if (paren_index := line.index("(")) == 0 or line[paren_index - 1] == " ":
            return False

        func_name = line.split("(")[0].split(" ")[-1]

        if func_name not in self._func_lut and func_name not in FUNCTIONS:
            raise ValueError(f"Function call for {func_name} not found. {self._func_lut}")

        return True

    def _try_bank_directive(self, lines: list[str]):
        if ".bank" not in lines[0]:
            return False

        line = strip_comment(lines.pop(0))
        self._print_line("Bank Start", line)
        _, bank_index = line.split(" ")

        while lines and (line := strip_comment(lines.pop(0))):
            self._line_co += 1
            if line.startswith(".org"):
                self._print_line("Bank Def Org", line)
                continue

            if _is_only_comment(line) or _is_empty_line(line):
                self._print_line("Empty Line", line)
                continue

            if not line.startswith(".include"):
                raise ValueError(f"Encountered unexpected line: '{line}' during bank definition.")

            self._print_line("Bank Def Incl", line)

            _, relative_path = line.split(" ")

            absolute_path = self._root_dir / relative_path.replace('"', "")

            self._prg_lut[int(bank_index)] = absolute_path

            line_count_before = self._line_co
            self._prg_pass_1(absolute_path)

            self._line_co = line_count_before

            if not absolute_path.is_file():
                raise ValueError(f"Could not load {absolute_path} correctly. Doesn't exist or is not a file.")

            return True
        else:
            raise ValueError(f"Ran out of lines in bank definition with index {bank_index}.")

    def _try_incchr_directive(self, lines: list[str]):
        if ".incchr" not in lines[0]:
            return False

        line = strip_comment(lines.pop(0))
        print(f"Char Mem Incl  {self._line_co}: {line}")

        _, relative_path = line.split(" ")

        absolute_path = self._root_dir / relative_path.replace('"', "")

        self._chr_lut.append(absolute_path)

        if not absolute_path.is_file():
            raise ValueError(f"Could not load {absolute_path} correctly. Doesn't exist or is not a file.")

        return True

    def _print_line(self, line_category: str, line: str):
        print(f"{line_category:<15}{self._line_co} | {self._current_byte_offset:x}: {line}")


ap = AssemblyParser(smb3_asm_file.absolute().parent)

ap.parse()
