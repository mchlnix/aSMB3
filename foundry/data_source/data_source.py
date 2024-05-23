"""
This is the interface for smb3 data. Both loading a ROM file and loading from an disassembly project should work the
same, since it is the same data, save for the text form of the PRG data in the disassembly.
"""

from abc import ABC


class DataSource(ABC):
    pass
