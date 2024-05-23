import re

from foundry.data_source import AsmPosition, _strip_comment


class Macro:
    def __init__(self, name, asm_position: AsmPosition):
        self.name = name
        self._position = asm_position
        self.lines: list[str] = []

    def expand(self, *args):
        expanded_lines = []

        for line in self.lines:
            if not line:
                continue

            for arg_no, arg in enumerate(args, 1):
                line = line.replace(f"\\{arg_no}", arg)

            expanded_lines.append(line)

        return expanded_lines

    @staticmethod
    def parse_macro(lines: list[str], asm_position: AsmPosition):
        lines = lines.copy()

        line = _strip_comment(lines.pop(0))
        name = Macro.macro_on_line(line)

        macro = Macro(name, asm_position)
        macro.lines.append(line)

        while lines:
            line = _strip_comment(lines.pop(0))
            macro.lines.append(line)

            if ".endm" in line:
                break
        else:
            raise ValueError(f"Ran out of lines in macro definition of {macro.name}.")

        return macro

    @staticmethod
    def _get_macro_args_in_line(line: str) -> list[str]:
        return re.findall("\\\\([0-9])", line)

    @staticmethod
    def macro_on_line(line: str):
        if ".macro" not in line:
            return ""

        return line.replace(".macro", "").strip()
