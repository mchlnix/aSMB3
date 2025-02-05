asm_file = open("/home/michael/Gits/smb3/PRG/prg004.asm")

asm_file_lines = asm_file.readlines()


def strip_line(line: str):
    """Remove whitespace and comments from a line."""

    line = line.strip()

    if ";" not in line:
        return line

    commment_start_index = line.find(";")

    return line[:commment_start_index].strip()


def is_label(line):
    if ":" not in line:
        return False

    colon_index = line.find(":")

    if " " in line[:colon_index]:
        return False

    return True


def is_byte_or_word(line):
    return line.startswith((".byte", ".word"))


def byte_or_word_value(line: str):
    return line.removeprefix(".byte").removeprefix(".word")


def should_ignore_line(line: str):
    # ignore empty lines
    if not line:
        return True

    # ignore comments
    if line.startswith(";"):
        return True

    # ignore asm specific directives
    if line.startswith(".org"):
        return True


if __name__ == "__main__":
    assert strip_line("  bla bla ; blabla") == "bla bla", strip_line("  bla bla ; blabla")

    have_seen_label = False
    last_label_name = ""
    in_a_jump_table = False
    decomp_line = ""

    for line_no, line in enumerate(asm_file_lines):
        decomp_line = ""

        line = strip_line(line)

        if should_ignore_line(line):
            continue

        if have_seen_label:
            if is_byte_or_word(line):
                in_a_jump_table = True
                print(f"{last_label_name} = [")
                have_seen_label = False
                last_label_name = ""

            elif is_label(line):
                # labels after each other mean basically variables with the same value
                have_seen_label = True
                print(f"{last_label_name} = ", end="")
                last_label_name = line.removesuffix(":")
                continue
        else:
            if in_a_jump_table and not is_byte_or_word(line):
                in_a_jump_table = False
                print("  ]")
                print()

            elif in_a_jump_table:
                decomp_line = f"  {byte_or_word_value(line)},"

            if is_label(line):
                have_seen_label = True
                last_label_name = line.removesuffix(":")
                continue

        have_seen_label = False

        if decomp_line:
            print(decomp_line)
        else:
            print(line_no, line)

        if line_no > 500:
            break
