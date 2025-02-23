#!/usr/bin/python3

from pathlib import Path

version_file_path = Path("VERSION")

assert version_file_path.exists(), "You need to be in the root of the repository."

current_version = version_file_path.read_text().strip()

new_version = input(f"What should the new version be (current: '{current_version}')? ")

assert current_version != new_version, "Versions are the same."

print(f"New version chosen: '{new_version}'.")

print("Updating VERSION file")

version_file_path.write_text(new_version + "\n")

print()
print("Next Steps:")

print("1. Commit the changes and push dev")
print("2. Merge the current dev into master.")
print("3. Make an annotated tag with the version number.")
print(f"4. First line should be '{new_version} Some codename'")
print("5. Then an empty line and beneath that the change notes.")
