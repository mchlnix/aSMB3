from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from foundry.data_source import OPERATORS, byte_length_of_number_string


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

    MACRO_PARAM = 9

    COMMENT = 50
    END = 99


class LeafType(Enum):
    ROOT = 0
    FUNCTION_NAME = 1
    SYMBOL = 2
    NUMBER = 3
    PARENS = 4
    FORMULA = 5
    FUNCTION_PARAMS = 6
    OPERATOR = 7
    LISTING = 8
    MACRO_PARAM = 9


@dataclass
class Leaf:
    value: str
    leaf_type: LeafType

    parent: "Leaf | None" = None
    leaves: list["Leaf"] = field(default_factory=list)


_VALID_END_STATES = [_ParseState.END, _ParseState.NEUTRAL]

_NUMERAL_START_CHARS = "$%+-"

_OPERATOR_NUMERAL_OVERLAY = set(OPERATORS).intersection(_NUMERAL_START_CHARS)


def _is_operator(char: str):
    return char in OPERATORS or char in "<>"


def _is_macro_param_start(char: str):
    return char == "\\"


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


class FormulaParser:
    LOGGING = False

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

        self.tree = Leaf("", LeafType.ROOT)
        self._current_leaf = self.tree

        self._state_func_lut: dict[_ParseState, Callable[[str], None]] = {
            _ParseState.NEUTRAL: self._do_neutral,
            _ParseState.SYMBOL: self._do_symbol,
            _ParseState.NUMERAL: self._do_numeral,
            _ParseState.BINARY: self._do_binary,
            _ParseState.DECIMAL: self._do_decimal,
            _ParseState.HEXADECIMAL: self._do_hexadecimal,
            _ParseState.FUNCTION_PARAMS: self._do_function_params,
            _ParseState.PARENS: self._do_parens,
            _ParseState.OPERATOR: self._do_operator,
            _ParseState.MACRO_PARAM: self._do_macro_param,
            _ParseState.COMMENT: self._do_comment,
        }

    def parse(self):
        self._current_char_index = 0

        while self._line and self._state != _ParseState.END:
            char = self._line[0]

            if self.LOGGING:
                print(f"Checking '{char}', {self._state}, {self._current_leaf}")

            if self._state not in self._state_func_lut:
                raise ValueError(f"No state matching for '{char}' / '{self._state.name}'")

            state_func = self._state_func_lut[self._state]

            state_func(char)

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
            if self._current_leaf.leaf_type == LeafType.FUNCTION_NAME:
                self._state = _ParseState.FUNCTION_PARAMS

            else:
                self._state = _ParseState.PARENS

        elif _is_close_parens(char):
            leaf = self._current_leaf

            while leaf.leaf_type != LeafType.ROOT:
                if leaf.leaf_type == LeafType.FUNCTION_PARAMS:
                    # finished function params, so go back to the parent of its function name
                    assert leaf.parent and leaf.parent.parent
                    new_current_leaf = leaf.parent.parent

                    break

                elif leaf.leaf_type == LeafType.PARENS:
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

        elif _is_macro_param_start(char):
            self._state = _ParseState.MACRO_PARAM

        elif char.isspace():
            self._skip()

        elif char == ",":
            self._maybe_insert_parent(LeafType.LISTING)
            self._skip()

        else:
            raise ValueError(f"Not sure what to do with '{char}'")

    def _maybe_insert_parent(self, leaf_type: LeafType):
        # 1./2. already inside what we want to insert
        if self._current_leaf.leaf_type == leaf_type:
            return

        # 3. after a formula, suddenly a listing
        if leaf_type == LeafType.LISTING and self._current_leaf.leaf_type == LeafType.FORMULA:
            cur_leaf = self._current_leaf
            assert cur_leaf.parent

            if cur_leaf.parent.leaf_type == LeafType.LISTING:
                # formula is already in a listing
                self._current_leaf = cur_leaf.parent
                return

        # 4. we can't be in a listing and want to make a formula its parent, because listings cannot be inside formulas,
        #    so take the last child of the listing instead, because it is the first operand of the formula
        # 5. nothing to consider, just insert new parent between current leaf and last child
        else:
            assert self._current_leaf.leaves
            cur_leaf = self._current_leaf.leaves[-1]

        self._insert_parent(cur_leaf, leaf_type)

    def _insert_parent(self, cur_leaf, leaf_type):
        old_parent = cur_leaf.parent
        new_parent = Leaf("", leaf_type)

        assert old_parent.leaves[-1] is cur_leaf

        # establish parent as old parents child
        new_parent.parent = old_parent
        old_parent.leaves.append(new_parent)

        # give current leaf from old parent to new parent
        old_parent.leaves.remove(cur_leaf)

        cur_leaf.parent = new_parent
        new_parent.leaves.append(cur_leaf)

        # set new current leaf
        self._current_leaf = new_parent

    def _do_macro_param(self, char: str):
        # expecting 1-9
        if self._current_leaf.leaf_type == LeafType.MACRO_PARAM:
            assert char.isnumeric() and char != "0", char

            self._take()

            self._end_macro_param()

        else:
            assert _is_macro_param_start(char)
            self._new_leaf(Leaf("", LeafType.MACRO_PARAM))

            self._take()

    def _end_macro_param(self):
        self._save_buffer(self._symbols)
        assert self._current_leaf.parent
        self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_symbol(self, char: str):
        if not _is_symbol_char(char):
            self._end_symbol(char)

        else:
            if self._current_leaf.leaf_type != LeafType.SYMBOL:
                self._new_leaf(Leaf("", LeafType.SYMBOL))

            self._take()

    def _end_symbol(self, char=""):
        if _is_open_parens(char):
            self._current_leaf.leaf_type = LeafType.FUNCTION_NAME
            self._save_buffer(self._function_names)
        else:
            self._save_buffer(self._symbols)
            assert self._current_leaf.parent
            self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_operator(self, char: str):
        if self._current_leaf.leaf_type != LeafType.OPERATOR:
            self._maybe_insert_parent(LeafType.FORMULA)

            leaf = Leaf("", LeafType.OPERATOR)
            self._new_leaf(leaf)

        # matches single character operators and the shift operators
        elif self._current_buffer + char in OPERATORS:
            self._take()

        elif self._current_buffer in OPERATORS:
            self._end_operator()

        elif char.isspace():
            self._skip()

        elif not self._current_buffer and char == ">":
            self._take()

        else:
            raise ValueError(f"What? '{char}'")

    def _end_operator(self):
        self._save_buffer(self._operators)

        assert self._current_leaf.parent
        self._current_leaf = self._current_leaf.parent

        self._state = _ParseState.NEUTRAL

    def _do_numeral(self, char: str):
        # covers numbers with a sign or binary numbers
        if char in _OPERATOR_NUMERAL_OVERLAY:
            not_a_new_list_element = self._current_leaf.leaf_type != LeafType.LIST or not self._last_char_was_comma
            will_not_be_first_leaf = bool(self._current_leaf.leaves)
            predecessor_can_precede_an_operand = will_not_be_first_leaf and self._current_leaf.leaves[-1].leaf_type in [
                LeafType.SYMBOL,
                LeafType.NUMBER,
                LeafType.PARENS,
            ]

            if not_a_new_list_element and will_not_be_first_leaf and predecessor_can_precede_an_operand:
                self._state = _ParseState.OPERATOR
            else:
                self._new_number_leaf()

                self._take()

            return

        if _is_hexadecimal_start(char):
            self._state = _ParseState.HEXADECIMAL

        elif _is_decimal_char(char):
            self._state = _ParseState.DECIMAL

        else:
            self._state = _ParseState.NEUTRAL

    def _do_function_params(self, _char: str):
        self._new_leaf(Leaf("()", LeafType.FUNCTION_PARAMS))

        self._skip()

        self._state = _ParseState.NEUTRAL

    def _do_parens(self, _char: str):
        self._new_leaf(Leaf("()", LeafType.PARENS))

        self._skip()

        self._state = _ParseState.NEUTRAL

    def _do_binary(self, char: str):
        if _is_binary_start(char):
            if self._current_leaf.leaf_type == LeafType.NUMBER:
                raise ValueError("Starting a binary number, while already doing that.")
            else:
                self._take()

        elif _is_binary_end(char):
            self._end_number()
        else:
            self._take()

    def _do_decimal(self, char: str):
        if self._current_leaf.leaf_type != LeafType.NUMBER:
            self._new_number_leaf()

        if _is_decimal_char(char):
            self._take()
        else:
            self._end_number()

    def _do_hexadecimal(self, char: str):
        if _is_hexadecimal_start(char):
            if self._current_buffer and _is_hexadecimal_start(self._current_buffer[-1]):
                raise ValueError("Starting a hexadecimal number, while already doing that.")

            elif self._current_leaf.leaf_type != LeafType.NUMBER:
                self._new_number_leaf()

            self._take()

        elif _is_hexadecimal_end(char):
            self._end_number()
        else:
            self._take()

    def _new_number_leaf(self):
        new_leaf = Leaf("", LeafType.NUMBER)
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
    def has_symbols(self):
        return self._has_type(LeafType.SYMBOL)

    @property
    def has_macro_params(self):
        return self._has_type(LeafType.MACRO_PARAM)

    def fill_in_symbols(self, symbols: dict[str, str]):
        for leaf in self._depth_first_tree_walk():
            if leaf.leaf_type != LeafType.SYMBOL:
                continue

            if leaf.value not in symbols:
                continue

            leaf.leaf_type = LeafType.NUMBER
            leaf.value = symbols[leaf.value]

    @staticmethod
    def _count_leaf_byte_size(leaf: Leaf):
        if leaf.leaf_type in (LeafType.ROOT, LeafType.FUNCTION_NAME, LeafType.PARENS, LeafType.FUNCTION_PARAMS):
            assert len(leaf.leaves) == 1
            return FormulaParser._count_leaf_byte_size(leaf.leaves[0])

        if leaf.leaf_type == LeafType.SYMBOL:
            raise ValueError(f"Couldn't determine byte size of Symbol '{leaf.value}'.")

        if leaf.leaf_type == LeafType.NUMBER:
            assert not leaf.leaves
            return byte_length_of_number_string(leaf.value)

        if leaf.leaf_type == LeafType.FORMULA:
            assert len(leaf.leaves) >= 2
            return max(FormulaParser._count_leaf_byte_size(leaf) for leaf in leaf.leaves)

        if leaf.leaf_type == LeafType.OPERATOR:
            assert not leaf.leaves
            return 0

        if leaf.leaf_type == LeafType.LISTING:
            assert len(leaf.leaves) >= 2
            return sum(FormulaParser._count_leaf_byte_size(leaf) for leaf in leaf.leaves)

        if leaf.leaf_type == LeafType.MACRO_PARAM:
            raise ValueError(f"Couldn't determine byte size of Macro Param '{leaf.value}'.")

    def _depth_first_tree_walk(self):
        leaves = self.tree.leaves.copy()

        while leaves:
            leaf = leaves.pop(0)

            yield leaf

            leaves.extend(leaf.leaves)

    def _has_type(self, leaf_type: LeafType):
        for leaf in self._depth_first_tree_walk():
            if leaf.leaf_type == leaf_type:
                return True

        else:
            return False

    @property
    def _last_part_was_operator(self):
        if not self.parts or not self._operators:
            return False

        return self.parts[-1] == self._operators[-1]

    def debug_str_tree(self):
        return self._debug_str_leaf(self.tree)

    def _debug_str_leaf(self, leaf: Leaf):
        return f"('{leaf.value}', {leaf.leaf_type.name}, l=[{', '.join(map(self._debug_str_leaf, leaf.leaves))}])"
