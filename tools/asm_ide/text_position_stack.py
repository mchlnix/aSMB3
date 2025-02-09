from pathlib import Path


class TextPositionStack:
    def __init__(self):
        self.stack: list[tuple[Path, int]] = []

        self.current_index = -1

    def push(self, file_path: Path, pos_in_text: int):
        self.truncate()

        self.stack.append((file_path, pos_in_text))
        self.current_index += 1

    def go_forward(self) -> tuple[Path, int]:
        self.current_index += 1

        return self.stack[self.current_index]

    def go_back(self) -> tuple[Path, int]:
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
