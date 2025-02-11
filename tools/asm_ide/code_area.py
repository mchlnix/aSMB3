from pathlib import Path

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QPlainTextDocumentLayout,
    QPlainTextEdit,
    QTextEdit,
    QToolTip,
)

from foundry import ctrl_is_pressed
from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter
from tools.asm_ide.line_number_area import LineNumberArea
from tools.asm_ide.named_value_finder import NamedValueFinder
from tools.asm_ide.search_bar import SearchBar


class CodeArea(QPlainTextEdit):
    text_position_clicked = Signal(int)
    """
    :param The block index the cursor was put to.
    """
    redirect_clicked = Signal(Path, int)
    """
    :param Path The relative file path to go to.
    :param int The line number to go to.
    """
    blockCountChanged: SignalInstance(int)
    cursorPositionChanged: SignalInstance()

    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(CodeArea, self).__init__(parent)

        self._named_value_finder = named_value_finder
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMouseTracking(True)

        # text document and font
        self.text_document = QTextDocument()
        self.text_document.setDocumentLayout(QPlainTextDocumentLayout(self.text_document))
        self.setDocument(self.text_document)

        self._font = QFont("Monospace", 14)
        self._font.setBold(True)
        self.text_document.setDefaultFont(self._font)

        # syntax highlighter
        self.syntax_highlighter = AsmSyntaxHighlighter(self, named_value_finder)
        self.syntax_highlighter.setDocument(self.text_document)

        # line number area
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._line_number_area.update_text_measurements)

        # word under cursor
        self.last_block: QTextBlock | None = None
        self.last_word = ""

        # extra current line and search highlighting
        self.cursorPositionChanged.connect(self._update_extra_selections)

        self._search_bar = SearchBar(self)
        self._search_bar.next_match.connect(self._search)
        self._search_bar.text_changed.connect(self._search)
        self._search_bar.text_changed.connect(self._update_extra_selections)
        self._search_bar.settings_changed.connect(self._update_extra_selections)
        self._search_bar.show()

        self._current_search_cursor: QTextCursor = QTextCursor()

    def focus_search_bar(self):
        self._search_bar.setFocus()

    def _search(self, direction=0):
        # todo use constants from SearchBar
        """
        Searches for the next instance of the search term in the search bar, if there is one.

        :param direction: Number between -1 and 1.
        `-1` means, search backwards.
        `0` means, stay with a word, as long as it continues to match, i.e. while typing (default).
        `1` means force to go to the next match if it exists (default behaviour of the QTextDocument.find function).
        """
        current_cursor = self.textCursor()

        # there is no neutral or default find flag, so we have to make our own
        find_flags = QTextDocument.FindFlag.FindBackward & QTextDocument.FindFlag.FindWholeWords

        if direction == -1:
            find_flags |= QTextDocument.FindFlag.FindBackward

        if current_cursor.hasSelection() and direction == 0:
            # QTextDocument.find() returns a text cursor, that already selects the search term.
            # When typing in a search term, with every new character, it would take the end of old match's the selection
            # and continue searching from there.
            # That means that even if you are already at a word matching the full search term you want to put in, it
            # will still jump to the next match if there is one.
            # So we need to move the current QTextCursor back by the length of the selected text, to give it a chance to
            # be found and selected again.
            selection_length = len(current_cursor.selectedText())

            current_cursor.movePosition(
                QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, selection_length
            )

        cursor_at_match = self.text_document.find(self._search_bar.search_term, current_cursor, find_flags)

        if cursor_at_match.isNull():
            return

        self.setTextCursor(cursor_at_match)

    def _update_extra_selections(self):
        selections = [self._get_current_line_highlight()]
        selections.extend(self._get_search_highlights())

        self.setExtraSelections(selections)

    def _get_search_highlights(self):
        search_term = self._search_bar.search_term

        if not search_term or not self._search_bar.should_highlight_all_matches:
            return [QTextEdit.ExtraSelection()]

        search_term_selections: list[QTextEdit.ExtraSelection] = []

        search_term_format = QTextCharFormat()
        search_term_format.setBackground(QBrush(QColor.fromRgb(255, 204, 255)))

        current_text_cursor = self.textCursor()
        current_text_cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)

        while not (next_match_cursor := self.text_document.find(search_term, current_text_cursor)).isNull():
            current_text_cursor = next_match_cursor

            search_term_selection = QTextEdit.ExtraSelection()

            search_term_selection.cursor = next_match_cursor
            search_term_selection.format = search_term_format

            search_term_selections.append(search_term_selection)

        return search_term_selections

    def _get_current_line_highlight(self):
        current_line_selection = QTextEdit.ExtraSelection()

        line_highlight_format = QTextCharFormat()
        line_highlight_format.setProperty(QTextFormat.FullWidthSelection, True)
        line_highlight_format.setBackground(QBrush(QColor(255, 255, 153)))

        current_line_selection.cursor = self.textCursor()
        current_line_selection.cursor.clearSelection()
        current_line_selection.format = line_highlight_format

        return current_line_selection

    def paintEvent(self, e: QPaintEvent):
        self._line_number_area.repaint()
        return super().paintEvent(e)

    def mouseMoveEvent(self, e):
        text_cursor = self.cursorForPosition(e.pos())

        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = text_cursor.selectedText().strip()

        if word == self.last_word:
            return super().mouseMoveEvent(e)

        # reset potentially old const highlighting
        self.last_word = ""
        self.syntax_highlighter.const_under_cursor = ""
        self.syntax_highlighter.ram_variable_under_cursor = ""
        self.syntax_highlighter.label_under_cursor = ""

        if self.last_block is not None:
            self.syntax_highlighter.rehighlightBlock(self.last_block)
            self.last_block = None

        self._update_tooltip(e, text_cursor, word)

        return super().mouseMoveEvent(e)

    def _update_tooltip(self, e, text_cursor, word):
        word_is_a_constant = word in self._named_value_finder.constants
        word_is_a_ram_variable = word in self._named_value_finder.ram_variables
        word_is_a_label = word in self._named_value_finder.labels

        if not (word_is_a_constant or word_is_a_ram_variable or word_is_a_label):
            self.setToolTip(None)
            return

        self.last_word = word
        tooltip = QToolTip()
        tooltip.setFont(QFont("Monospace", 14))

        if word_is_a_constant:
            name, value, file, line_no = self._named_value_finder.constants[word]
            self.syntax_highlighter.const_under_cursor = word
        elif word_is_a_ram_variable:
            name, value, file, line_no = self._named_value_finder.ram_variables[word]
            self.syntax_highlighter.ram_variable_under_cursor = word
        else:
            name, value, file, line_no = self._named_value_finder.labels[word]
            self.syntax_highlighter.label_under_cursor = word

        tooltip.showText(e.globalPos(), f"{file}+{line_no}: {name} = {value}", self)

        self.last_block = text_cursor.block()
        self.syntax_highlighter.rehighlightBlock(self.last_block)

    def mousePressEvent(self, event: QMouseEvent):
        text_cursor_at_click = self.cursorForPosition(event.pos())

        cursor_pos_changed = text_cursor_at_click.position() != self.textCursor().position()
        navigated_by_mouse = event.buttons() & (Qt.MouseButton.BackButton | Qt.MouseButton.ForwardButton)

        if cursor_pos_changed and not navigated_by_mouse:
            # todo: could be done with signal of QPlainTextEdit
            self.text_position_clicked.emit(text_cursor_at_click.position())

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, e):
        text_cursor = self.cursorForPosition(e.pos())
        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = text_cursor.selectedText().strip()

        if word in self._named_value_finder.constants:
            info = self._named_value_finder.constants[word]
        elif word in self._named_value_finder.labels:
            info = self._named_value_finder.labels[word]
        else:
            return super().mouseReleaseEvent(e)

        if not ctrl_is_pressed():
            return super().mouseReleaseEvent(e)

        _, _, relative_file_path, line_no = info

        self.redirect_clicked.emit(relative_file_path, line_no)

        return super().mouseReleaseEvent(e)

    def resizeEvent(self, event: QResizeEvent):
        self._search_bar.update_position()
        return event
