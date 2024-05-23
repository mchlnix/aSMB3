from smb3parse.types import NormalizedAddress

from .data_source import DataSource


class Disassembly(DataSource):
    def _get_file_from_offset(self, offset: NormalizedAddress) -> str:
        _prg_number = offset

        return ""
