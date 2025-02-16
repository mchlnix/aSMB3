from pathlib import Path
from random import seed

import pytest
from PySide6.QtGui import QPixmap

from approval_tests.gui import ApprovalDialog
from foundry import root_dir
from foundry.data_source.rom import ROM
from foundry.game.level.Level import Level
from foundry.gui.FoundryMainWindow import FoundryMainWindow
from smb3parse.objects.object_set import PLAINS_OBJECT_SET

test_rom_path = root_dir / "roms" / "SMB3.nes"

assert test_rom_path.exists(), f"The test suite needs a SMB3(U) Rom at '{test_rom_path}' to run."

level_1_1_object_address = 0x1FB92
level_1_1_enemy_address = 0xC537

level_1_2_object_address = 0x20F3A
level_1_2_enemy_address = 0xC6BA


@pytest.fixture(scope="session", autouse=True)
def seed_random():
    seed(0)


@pytest.fixture
def level(rom, qtbot):
    return Level(
        "Level 1-1",
        level_1_1_object_address,
        level_1_1_enemy_address,
        PLAINS_OBJECT_SET,
    )


@pytest.fixture()
def rom():
    ROM.load_from_file(test_rom_path)

    yield ROM()


def compare_images(image_name: str, ref_image_path: str, gen_image: QPixmap):
    if Path(ref_image_path).exists():
        result = ApprovalDialog.compare(image_name, QPixmap(ref_image_path), gen_image)

        if result == ApprovalDialog.DialogCode.Rejected:
            pytest.fail(f"{image_name} did not look like the reference.")
        elif result == ApprovalDialog.Overwrite:
            # accepted and overwrite ref
            gen_image.toImage().save(ref_image_path)
        elif result == ApprovalDialog.Ignore:
            pytest.skip(f"{image_name} did not look like the reference, but was ignored.")
        else:
            pass

    else:
        gen_image.toImage().save(ref_image_path)

        pytest.skip(f"No ref image was found. Saved new ref under {ref_image_path}.")


@pytest.fixture
def main_window(qtbot, rom):
    # mock the rom loading, since it is a modal dialog. the rom is loaded in conftest.py
    setattr(FoundryMainWindow, "on_open_rom", lambda *_: None)
    setattr(FoundryMainWindow, "showMaximized", lambda _: None)  # don't open automatically
    setattr(FoundryMainWindow, "safe_to_change", lambda _: True)  # don't ask for confirmation on changed level
    setattr(FoundryMainWindow, "check_for_update_on_startup", lambda _: True)  # don't check for update

    main_window = FoundryMainWindow()
    main_window.update_level(
        "Level 1-1",
        level_1_1_object_address,
        level_1_1_enemy_address,
        PLAINS_OBJECT_SET,
    )

    qtbot.addWidget(main_window)

    return main_window
