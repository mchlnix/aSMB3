from dataclasses import dataclass, field
from enum import Enum

from foundry.data_source import OPERATORS


class _ParseState(Enum):
    NEUTRAL = 0
    SYMBOL = 1

    BINARY = 2
    DECIMAL = 3
    HEXADECIMAL = 4

    NUMERAL = 5

    FUNCTION_PARAMS = 6

    PARENS = 7

    OPERATOR = 8

    COMMENT = 50
    END = 99


class _LeafType(Enum):
    ROOT = 0
    FUNCTION_NAME = 1
    SYMBOL = 2
    NUMBER = 3
    PARENS = 4
    FORMULA = 5
    FUNCTION_PARAMS = 6
    OPERATOR = 7
    LISTING = 8


@dataclass
class Leaf:
    value: str
    leaf_type: _LeafType

    parent: "Leaf | None" = None
    leaves: list["Leaf"] = field(default_factory=list)


_VALID_END_STATES = [_ParseState.END, _ParseState.NEUTRAL]

_NUMERAL_START_CHARS = "$%+-"

_OPERATOR_NUMERAL_OVERLAY = set(OPERATORS).intersection(_NUMERAL_START_CHARS)


def _is_operator(char: str):
    return char in OPERATORS or char in "<>"


def _is_numeral_start(char: str):
    return char in _NUMERAL_START_CHARS or char.isnumeric()


def _is_binary_start(char):
    return char == "%"


def _is_binary_end(char):
    return char not in ["0", "1"]


def _is_decimal_char(char: str):
    return char.isnumeric()


def _is_hexadecimal_start(char):
    return char == "$"


def _is_hexadecimal_end(char):
    return not char.isnumeric() and char.upper() not in "ABCDEF"


def _is_symbol_start(char: str):
    return char.isalpha() or char == "_"


def _is_symbol_char(char: str):
    return char.isalnum() or char == "_"


def _is_open_parens(char: str):
    return char == "("


def _is_close_parens(char: str):
    return char == ")"


def _is_function_params_end(char: str):
    return _is_close_parens(char)


class FormulaParser:
    def __init__(self, line: str):
        self._line = line

        self._function_names: list[str] = []
        self._functions_params: list[str] = []
        self._numbers: list[str] = []
        self._operators: list[str] = []
        self._symbols: list[str] = []

        self.parts: list[str] = []

        self._state = _ParseState.NEUTRAL

        self._current_char_index = 0

        self._last_char_was_comma = True
        """
        Makes more sense this way. There is probably a better name for this condition than pinning it on the comma.
        """

        self.tree = Leaf("", _LeafType.ROOT)
        self._current_leaf = self.tree

    def parse(self):
        self._current_char_index = 0

        while self._line and self._state != _ParseState.END:
            char = self._line[0]

            # print(f"Checking '{char}', {self._state}, {self._current_leaf}")

            if self._state == _ParseState.NEUTRAL:
                self._do_neutral(char)

            elif self._state == _ParseState.SYMBOL:
                self._do_symbol(char)

            elif self._state == _ParseState.NUMERAL:
                self._do_numeral(char)

            elif self._state == _ParseState.BINARY:
                self._do_binary(char)

            elif self._state == _ParseState.DECIMAL:
                self._do_decimal(char)

            elif self._state == _ParseState.HEXADECIMAL:
                self._do_hexadecimal(char)

            elif self._state == _ParseState.FUNCTION_PARAMS:
                self._do_function_params(char)

            elif self._state == _ParseState.PARENS:
                self._do_parens(char)

            elif self._state == _ParseState.OPERATOR:
                self._do_operator(char)

            elif self._state == _ParseState.COMMENT:
                self._do_comment(char)

            else:
                raise ValueError(f"No state matching for '{char}' / '{self._state.name}'")

        if self._state == _ParseState.SYMBOL:
            self._end_symbol()

        elif self._state in [_ParseState.BINARY, _ParseState.DECIMAL, _ParseState.HEXADECIMAL]:
            self._end_number()

        if self._state not in _VALID_END_STATES:
            raise ValueError("Ran out of characters")

    def _do_neutral(self, char: str):
        if _is_symbol_start(char):
            self._state = _ParseState.SYMBOL

        elif _is_numeral_start(char):
            self._state = _ParseState.NUMERAL

        elif _is_open_parens(char):
            if self._current_leaf.leaf_type == _LeafType.FUNCTION_NAME:
                self._state = _ParseState.FUNCTION_PARAMS

            else:
                self._state = _ParseState.PARENS

        elif _is_close_parens(char):
            leaf = self._current_leaf

            while leaf.leaf_type != _LeafType.ROOT:
                if leaf.leaf_type == _LeafType.FUNCTION_PARAMS:
                    # finished function params, so go back to parent of it's function name
                    assert leaf.parent and leaf.parent.parent
                    new_current_leaf = leaf.parent.parent

                    break

                elif leaf.leaf_type == _LeafType.PARENS:
                    # close the parenthesis around whatever this was, probably a calculation
                    assert leaf.parent
                    new_current_leaf = leaf.parent

                    break

                else:
                    assert leaf.parent
                    leaf = leaf.parent
            else:
                raise ValueError("Couldn't find leaf with opening parenthesis for the found closing parenthesis.")

            self._current_leaf = new_current_leaf
            self._skip()
            self._state = _ParseState.NEUTRAL

        elif char == ";":
            self._state = _ParseState.COMMENT

        elif _is_operator(char):
            self._state = _ParseState.OPERATOR

        elif char.isspace():
            self._skip()

        elif char == ",":
            self._insert_listing(char)

        else:
            raise ValueError(f"Not sure what to do with '{char}'")

    def _insert_listing(self, _char: str):
        assert self._state == _ParseState.NEUTRAL

        last_leaf = self._current_leaf.leaves[-1]

        if self._current_leaf.leaf_type != _LeafType.LISTING:
            # replace last leaf at parent with new listing leaf
            assert last_leaf.parent
            assert last_leaf.parent.leaves.pop() == last_leaf

            if self._current_leaf.leaves and self._current_leaf.leaves[-1].leaf_type == _LeafType.LISTING:
                new_leaf = self._current_leaf.leaves[-1]
            else:
                new_leaf = Leaf("", _LeafType.LISTING)
                new_leaf.parent = self._current_leaf
                last_leaf.parent.leaves.append(new_leaf)

            # replace parent at last leave with new listing leaf
            new_leaf.leaves.append(last_leaf)
            last_leaf.parent = new_leaf

            self._current_leaf = new_leaf

        self._skip()

    def _do_symbol(self, char: str):
        if not _is_symbol_char(char):
            self._end_symbol(char)

        else:
            if self._current_leaf.leaf_type != _LeafType.SYMBOL:
                self._new_leaf(Leaf("", _LeafType.SYMBOL))

            self._take()

    def _end_symbol(self, char=""):
        self._current_leaf.value = self._current_buffer

        if _is_open_parens(char):
            self._current_leaf.leaf_type = _LeafType.FUNCTION_NAME
            self._save_buffer(self._function_names)
        else:
            self._save_buffer(self._symbols)
            assert self._current_leaf.parent
            self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_operator(self, char: str):
        if self._current_leaf.leaf_type != _LeafType.OPERATOR:
            leaf = Leaf("", _LeafType.OPERATOR)
            self._new_leaf(leaf)

        if char not in "<>" and self._last_part_was_operator:
            self._end_operator()

        elif self._current_buffer + char in OPERATORS:
            self._take()

        elif char.isspace():
            self._skip()

        elif self._current_buffer in OPERATORS:
            self._end_operator()

        elif not self._current_buffer and char == ">":
            self._take()

        else:
            raise ValueError(f"What? '{char}'")

    def _end_operator(self):
        self._save_buffer(self._operators)

        self._current_leaf.value = self._current_buffer
        assert self._current_leaf.parent
        self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_numeral(self, char: str):
        if char in _OPERATOR_NUMERAL_OVERLAY:
            if not self._last_char_was_comma or self._last_part_was_operator:
                self._state = _ParseState.OPERATOR
            else:
                self._new_number_leaf()

                self._take()

            return

        if not (_is_binary_start(char) or _is_hexadecimal_start(char) or _is_decimal_char(char)):
            self._take()

        if _is_binary_start(char):
            self._state = _ParseState.BINARY

        elif _is_hexadecimal_start(char):
            self._state = _ParseState.HEXADECIMAL

        elif _is_decimal_char(char):
            self._state = _ParseState.DECIMAL

        else:
            self._state = _ParseState.NEUTRAL

    def _do_function_params(self, _char: str):
        self._new_leaf(Leaf("()", _LeafType.FUNCTION_PARAMS))

        self._skip()

        self._state = _ParseState.NEUTRAL

    def _do_parens(self, _char: str):
        self._new_leaf(Leaf("()", _LeafType.PARENS))

        self._skip()

        self._state = _ParseState.NEUTRAL

    def _do_binary(self, char: str):
        if _is_binary_start(char):
            if self._current_leaf.leaf_type == _LeafType.NUMBER:
                raise ValueError("Starting a binary number, while already doing that.")
            else:
                self._take()

        elif _is_binary_end(char):
            self._end_number()
        else:
            self._take()

    def _do_decimal(self, char: str):
        if self._current_leaf.leaf_type != _LeafType.NUMBER:
            self._new_number_leaf()

        if _is_decimal_char(char):
            self._take()
        else:
            self._end_number()

    def _do_hexadecimal(self, char: str):
        if _is_hexadecimal_start(char):
            if self._current_buffer and _is_hexadecimal_start(self._current_buffer[-1]):
                raise ValueError("Starting a hexadecimal number, while already doing that.")

            elif self._current_leaf.leaf_type != _LeafType.NUMBER:
                self._new_number_leaf()

            self._take()

        elif _is_hexadecimal_end(char):
            self._end_number()
        else:
            self._take()

    def _new_number_leaf(self):
        new_leaf = Leaf("", _LeafType.NUMBER)
        self._new_leaf(new_leaf)

    def _end_number(self):
        self._save_buffer(self._numbers)

        assert self._current_leaf.parent
        self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_comment(self, _char: str):
        self._state = _ParseState.END

    def _take(self):
        self._current_buffer += self._line[0]
        self._skip()

    def _skip(self):
        char = self._line[0]

        if not char.isspace():
            self._last_char_was_comma = char == ","

        self._line = self._line[1:]

    def _save_buffer(self, location: list):
        self.parts.append(self._current_buffer)

        location.append(self._current_buffer)

    def _new_leaf(self, leaf: Leaf):
        self._current_leaf.leaves.append(leaf)
        leaf.parent = self._current_leaf

        self._current_leaf = leaf

    @property
    def _current_buffer(self):
        return self._current_leaf.value

    @_current_buffer.setter
    def _current_buffer(self, value):
        self._current_leaf.value = value

    @property
    def _last_part_was_operator(self):
        if not self.parts or not self._operators:
            return False

        return self.parts[-1] == self._operators[-1]

    def debug_str_tree(self):
        return self._debug_str_leaf(self.tree)

    def _debug_str_leaf(self, leaf: Leaf):
        return f"('{leaf.value}', {leaf.leaf_type.name}, l=[{', '.join(map(self._debug_str_leaf, leaf.leaves))}])"
