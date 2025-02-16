from pathlib import Path
from typing import NamedTuple


class TextPosition(NamedTuple):
    file_path: Path
    pos_in_text: int


class TextPositionStack:
    def __init__(self):
        self.stack: list[TextPosition] = []

        self.current_index = -1

        self.overwrite_position_at_top_of_the_file = True
        """
        When a new position is pushed for a file, and the last position on the stack was for the same file at position
        0, so at the beginning of the file, then drop that one and overwrite it with the given position.

        Idea behind that is, that when a new file is opened, it make sense to add a position there, but as soon as the
        user sets one themselves, it's bothersome to have this unintended position in the stack.
        """

    def push(self, file_path: Path, pos_in_text: int):
        self.truncate()

        if self.overwrite_position_at_top_of_the_file and self.stack:
            head = self.stack[self.current_index]

            if head.file_path == file_path and head.pos_in_text == 0:
                self.go_back()
                self.push(file_path, pos_in_text)

                return

        self.stack.append(TextPosition(file_path, pos_in_text))
        self.current_index += 1

    def go_forward(self) -> TextPosition:
        self.current_index += 1

        return self.stack[self.current_index]

    def go_back(self) -> TextPosition:
        self.current_index -= 1

        return self.stack[self.current_index]

    def truncate(self):
        if self.current_index == len(self.stack) - 1:
            return

        self.stack = self.stack[: self.current_index + 1]

    def is_at_the_beginning(self):
        return self.current_index < 1

    def is_at_the_end(self):
        return self.current_index == len(self.stack) - 1
