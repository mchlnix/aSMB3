from typing import Generator

from PySide6.QtCore import QRegularExpression, QRegularExpressionMatchIterator
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from tools.asm_ide.reference_finder import (
    ReferenceDefinition,
    ReferenceFinder,
    ReferenceType,
)
from tools.asm_ide.util import is_generic_directive, is_instruction

_DEC_NUMBER_REGEX = QRegularExpression("([0-9]+)")
_HEX_NUMBER_REGEX = QRegularExpression("(\$[A-Fa-f0-9]+)")
_BIN_NUMBER_REGEX = QRegularExpression("(\%[0-1]+)")
_CONST_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\s*\=")
_DIRECTIVE_REGEX = QRegularExpression("(\.[A-Za-z_][A-Za-z]*)")
_STRING_REGEX = QRegularExpression('("[^"]*")')
_COMMENT_REGEX = QRegularExpression("(;.*)")
_LABEL_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:")
_CONST_LABEL_CALL_RAM_VAR_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)")


_DEC_NUMBER_COLOR = QColor.fromRgb(255, 0, 0)
_HEX_NUMBER_COLOR = QColor.fromRgb(0x986800)
_BIN_NUMBER_COLOR = QColor.fromRgb(0x2C91AF)
_CONST_COLOR = QColor.fromRgb(0, 51, 204)
_DIRECTIVE_COLOR = QColor.fromRgb(0xA626A4)
_STRING_COLOR = QColor.fromRgb(0x50A14F)
_COMMENT_COLOR = QColor.fromRgb(0xA0A1A7)
_LABEL_COLOR = QColor.fromRgb(0xA626A4)
_RAM_VARIABLE_COLOR = QColor.fromRgb(0xE45649)

_INSTRUCTION_COLOR = QColor.fromRgb(0x3E4047)

_DEFAULT_TEXT_COLOR = QColor.fromRgb(0x383A42)


_CLICKABLE_CONST_COLOR = QTextCharFormat()
_CLICKABLE_CONST_COLOR.setForeground(_CONST_COLOR)
_CLICKABLE_CONST_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_CLICKABLE_LABEL_COLOR = QTextCharFormat()
_CLICKABLE_LABEL_COLOR.setForeground(_LABEL_COLOR)
_CLICKABLE_LABEL_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_CLICKABLE_RAM_VAR_COLOR = QTextCharFormat()
_CLICKABLE_RAM_VAR_COLOR.setForeground(_RAM_VARIABLE_COLOR)
_CLICKABLE_RAM_VAR_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_REGEXS = [
    _DEC_NUMBER_REGEX,
    _HEX_NUMBER_REGEX,
    _BIN_NUMBER_REGEX,
    _CONST_DEF_REGEX,
    _DIRECTIVE_REGEX,
    _LABEL_DEF_REGEX,
    _CONST_LABEL_CALL_RAM_VAR_REGEX,
    _STRING_REGEX,
    _COMMENT_REGEX,
]

_COLORS = [
    _DEC_NUMBER_COLOR,
    _HEX_NUMBER_COLOR,
    _BIN_NUMBER_COLOR,
    _CONST_COLOR,
    _DIRECTIVE_COLOR,
    _LABEL_COLOR,
    _CONST_COLOR,  # Not actually used, this will be coloured, depending on what is found
    _STRING_COLOR,
    _COMMENT_COLOR,
]

_REF_TYPE_TO_COLOR = {
    ReferenceType.CONSTANT: _CONST_COLOR,
    ReferenceType.RAM_VAR: _RAM_VARIABLE_COLOR,
    ReferenceType.LABEL: _LABEL_COLOR,
}


class AsmSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, reference_finder: ReferenceFinder):
        super(AsmSyntaxHighlighter, self).__init__(parent)

        self._reference_finder = reference_finder

        self.reference_under_cursor: ReferenceDefinition | None = None

    def highlightBlock(self, line: str, clickable=False):
        self.setFormat(0, len(line) - 1, _DEFAULT_TEXT_COLOR)

        self._format_instructions_in_line(line)
        self._format_directives_in_line(line)

        for expression, color in zip(_REGEXS, _COLORS, strict=True):
            match_iterator = expression.globalMatch(line)

            for capture_start, capture_length, capture_text in self._iter_matches(match_iterator):
                # intervene, if this is a constant, ram variable or label under the mouse cursor
                if expression != _CONST_LABEL_CALL_RAM_VAR_REGEX:
                    self.setFormat(capture_start, capture_length, color)
                    continue

                if capture_text not in self._reference_finder.definitions:
                    continue

                if self.reference_under_cursor and capture_text == self.reference_under_cursor.name:
                    self._format_reference_under_cursor(capture_length, capture_start)
                    continue

                *_, ref_type, _ = self._reference_finder.definitions[capture_text]

                if ref_type not in _REF_TYPE_TO_COLOR:
                    continue

                self.setFormat(capture_start, capture_length, _REF_TYPE_TO_COLOR[ref_type])

    def _format_instructions_in_line(self, line):
        if not is_instruction(line):
            return

        start = 0
        end = line.find(" ", start)
        instruction_length = end - start

        self.setFormat(start, instruction_length, _INSTRUCTION_COLOR)

    def _format_directives_in_line(self, line):
        if not is_generic_directive(line.strip()):
            return

        start = line.find(".")
        end = line.find(" ", start)
        directive_length = end - start

        self.setFormat(start, directive_length, _DIRECTIVE_COLOR)

    def _format_reference_under_cursor(self, capture_length, capture_start):
        if self.reference_under_cursor is None:
            return

        if self.reference_under_cursor.type == ReferenceType.CONSTANT:
            text_format = _CLICKABLE_CONST_COLOR
        elif self.reference_under_cursor.type == ReferenceType.RAM_VAR:
            text_format = _CLICKABLE_RAM_VAR_COLOR
        else:
            text_format = _CLICKABLE_LABEL_COLOR

        self.setFormat(capture_start, capture_length, text_format.toCharFormat())

    @staticmethod
    def _iter_matches(match_iterator: QRegularExpressionMatchIterator) -> Generator[tuple[int, int, str], None, None]:
        while match_iterator.hasNext():
            match = match_iterator.next()

            # skip the 0th capture group, which is the whole match
            for index in range(1, match.lastCapturedIndex() + 1):
                yield match.capturedStart(index), match.capturedLength(index), match.capturedView(index).strip()
