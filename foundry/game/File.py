import json
from collections import defaultdict
from operator import attrgetter
from os.path import basename
from pathlib import Path
from typing import Optional

from smb3parse import PAGE_A000_ByTileset
from smb3parse.constants import BASE_OFFSET
from smb3parse.util.parser import FoundLevel
from smb3parse.util.rom import INESHeader, PRG_BANK_SIZE, Rom


class AdditionalData:
    """
    Set of additional, foundry specific data, meant to persist between invocations of the editor. Can be used to keep
    ROM specific decisions or settings, that have no place in the actual game data.
    """

    def __init__(self):
        self.managed_level_positions: bool | None = None
        """
        If this is True, then the positions of the level data in the ROM is completely managed by the editor. The old
        way of remembering the position of a level, while editing, and manually opening it using this address will not
        work with this.
        """

        self.found_level_information: list[FoundLevel] = []

    def __str__(self) -> str:
        return json.dumps(
            {
                "managed_level_positions": self.managed_level_positions,
                "found_level_information": [found_level.to_dict() for found_level in self.found_level_information],
            }
        )

    @staticmethod
    def from_str(string_data: str) -> "AdditionalData":
        data_obj = AdditionalData()

        data_dict = json.loads(string_data)

        data_obj.managed_level_positions = data_dict.get("managed_level_positions", None)
        data_obj.found_level_information = [
            FoundLevel.from_dict(data) for data in data_dict.get("found_level_information", [])
        ]

        return data_obj

    def __bool__(self):
        return bool(self.managed_level_positions and self.found_level_information)

    def clear(self):
        self.managed_level_positions = None
        self.found_level_information.clear()


class MovableLevel(FoundLevel):
    new_level_offset: int
    level_data: bytearray
    level_base: FoundLevel

    @staticmethod
    def from_found_level(level: FoundLevel, new_level_offset: int = 0):
        ret_level = MovableLevel([], [], 0, 0, 0, 0, 0, False, False, False)

        ret_level.__dict__.update(vars(level))

        ret_level.level_base = level
        ret_level.new_level_offset = new_level_offset
        ret_level.level_data = bytearray()

        return ret_level

    def update_level_offset(self, value):
        self.level_base.level_offset = value


class ROM(Rom):
    MARKER_VALUE = bytes("SMB3FOUNDRY", "ascii")
    PRG030_INDEX = -2
    """The index passed to search_bank to search the vanilla prg030 bank, regardless of expanded ROM"""
    PRG031_INDEX = -1
    """The index passed to search_bank to search the vanilla prg031 bank, regardless of expanded ROM"""

    rom_data = bytearray()
    header: Optional[INESHeader] = None

    additional_data = AdditionalData()

    path: str = ""
    name: str = ""

    W_INIT_OS_LIST: list[int] = []

    def __init__(self, path: Path | str | None = None):
        if not ROM.rom_data:
            if path is None:
                raise ValueError("Rom was not loaded!")

            ROM.load_from_file(path)

        super(ROM, self).__init__(ROM.rom_data, ROM.header)

    @staticmethod
    def get_tsa_data(object_set: int) -> bytes:
        """Returns bytes, instead of bytearray, because bytes is hashable. FIXME?"""
        rom = ROM()

        return bytes(rom.tsa_data_for_object_set(object_set))

    @staticmethod
    def load_from_file(path: Path | str):
        with open(path, "rb") as rom:
            data = bytearray(rom.read())

        ROM.header = INESHeader.from_buffer_copy(data)
        ROM.path = str(path)
        ROM.name = basename(path)

        additional_data_start = data.find(ROM.MARKER_VALUE)

        if additional_data_start == -1:
            ROM.rom_data = data
            ROM.additional_data = AdditionalData()
        else:
            ROM.rom_data = data[:additional_data_start]

            additional_data_start += len(ROM.MARKER_VALUE)

            ROM.additional_data = AdditionalData.from_str(data[additional_data_start:].decode("utf-8"))

    @staticmethod
    def reload_from_file():
        additional_data = ROM.additional_data

        if ROM.path:
            ROM.load_from_file(ROM.path)

        ROM.additional_data = additional_data

    @staticmethod
    def save_to_file(path: Path | str, set_new_path=True):
        Path(path).open("wb").write(bytearray(ROM.rom_data))

        if ROM.additional_data:
            with open(path, "ab") as f:
                f.write(ROM.MARKER_VALUE)
                f.write(str(ROM.additional_data).encode("utf-8"))

        if set_new_path:
            ROM.path = str(path)
            ROM.name = basename(path)

    @staticmethod
    def is_loaded() -> bool:
        return bool(ROM.path)

    def rearrange_levels(self):
        # 0. Sort Levels by bank
        prg_banks_by_object_set = self.read(PAGE_A000_ByTileset, 16)

        levels_by_bank: dict[int, list[MovableLevel]] = defaultdict(list)

        for level in self.additional_data.found_level_information:
            levels_by_bank[prg_banks_by_object_set[level.object_set_number]].append(
                MovableLevel.from_found_level(level)
            )

        # 1. Go through each bank one by one
        for bank, levels in levels_by_bank.items():
            print(f"Doing Bank {bank}")
            object_set_offset = BASE_OFFSET + bank * PRG_BANK_SIZE - 0xA000

            # 2. Take all the levels and sort them by address
            levels.sort(key=attrgetter("level_offset"))

            # 3. Take the first one as the bank start
            first_level = levels[0]
            last_level_end = first_level.level_offset + first_level.byte_length + 1

            # 4. Compute and update level position in all its pointers
            for level in levels[1:]:
                for pointer_to_level in level.level_offset_positions:
                    self.write_little_endian(pointer_to_level, last_level_end - object_set_offset)

                level.new_level_offset = last_level_end

                last_level_end += level.byte_length + 1

        for bank, levels in levels_by_bank.items():
            print(f"Doing Bank {bank}")

            # 2. Take all the levels and sort them by address
            levels.sort(key=attrgetter("level_offset"))

            for level in levels[1:]:
                print(hex(level.level_offset), "->", hex(level.new_level_offset))

                level.level_data = self.read(level.level_offset, level.byte_length + 1)

            for level in levels[1:]:
                level.update_level_offset(level.new_level_offset)

                self.write(level.new_level_offset, level.level_data)

        self.save_to_file(ROM.path)

    def search_bank(self, needle: bytes, bank: int) -> int:
        """Search a specific bank given a zero-based bank index.
        If negative values are used, -1 is the last bank, -2 is the second-to-last bank, etc.
        """
        num_prg_banks = ROM().prg_banks
        # Mod here for negative banks (negative indices index from the end)
        bank = bank % num_prg_banks

        if bank not in range(num_prg_banks):
            return -1

        start = bank * PRG_BANK_SIZE
        return self.find(needle, start, start + PRG_BANK_SIZE)
