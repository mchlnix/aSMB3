"""
This is the interface for smb3 data. Both loading a ROM file and loading from an disassembly project should work the
same, since it is the same data, save for the text form of the PRG data in the disassembly.
"""

from abc import ABC
from pathlib import Path

from foundry.data_source.assembly_parser import AssemblyParser
from smb3parse.util.rom import INESHeader


class DataSource(ABC):
    pass


class AssemblyByteArray(bytearray):
    def __init__(self, path_to_smb3_asm: Path):
        self.path_to_smb3_asm = path_to_smb3_asm.parent

        self._ap = AssemblyParser(self.path_to_smb3_asm)
        self._ap.parse()

        super().__init__()

    def __bool__(self):
        return True

    def __buffer__(self, __flags):
        return bytearray(16)

    def __bytes__(self):
        return bytes(16)

    def __len__(self):
        return self._ap._current_byte_offset

    def __getitem__(self, item):
        if isinstance(item, int):
            if item < INESHeader.LENGTH:
                return self._ap.ines_header[item]

            closest_position = self._ap.closest_pos_for_byte(item)

            print(item, "->", closest_position, flush=True)

        else:
            if item.stop is None:
                stop = item.start + 1
            else:
                stop = item.stop

            if item.step is None:
                step = 1
            else:
                step = item.step

            for index in range(item.start, stop, step):
                closest_position = self._ap.closest_pos_for_byte(index)
                print(item, "->", closest_position, flush=True)

        raise ValueError("Bro")

    def __slice__(self, __start, __end):
        raise ValueError
