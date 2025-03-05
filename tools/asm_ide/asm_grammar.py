from pathlib import Path
from time import time

from parsimonious.grammar import Grammar

from tools.asm_ide.util import DIRECTIVES, INSTRUCTIONS, apply


def _wrap_in_quotes(text: str) -> str:
    return '"' + text + '"'


QUOTED_DIRECTIVES = apply(_wrap_in_quotes, DIRECTIVES)
QUOTED_INSTRUCTIONS = apply(_wrap_in_quotes, INSTRUCTIONS)
asm_grammar = Grammar(
    f"""
    program               = (line / empty_line / comment_line)*

    empty_line            = newline
    comment_line          = ws? comment newline
    line                  = ws? (symbol_def / orphaned_bytes / orphaned_words / directive_use / instruction_use / macro_use) comment? newline

    ws                    = ~r"\\h*"
    newline               = ws? ("\\r\\n" / "\\n")

    comment               = ws? ";" ws? everything?
    everything            = ~".*"

    instruction_use       = instruction (ws ("#" / "<")? (expression / indirect_address) (ws? "," ws? register)?)?
    indirect_address      = "[" symbol "]"
    instruction           = {" / ".join(QUOTED_INSTRUCTIONS)} / {" / ".join(map(str.lower, QUOTED_INSTRUCTIONS))} / unknown_symbol
    register              = "X" / "Y"
    unknown_symbol          = symbol

    directive_use         = dot_include / dot_ds / dot_incchr / dot_org / (directive (ws number_literal)?)
    directive             = {" / ".join(QUOTED_DIRECTIVES)} / {" / ".join(map(str.lower, QUOTED_DIRECTIVES))}

    dot_byte              = ".byte" ws expression_list comment?
    dot_word              = ".word" ws expression_list comment?

    orphaned_bytes        = dot_byte
    orphaned_words        = dot_word

    dot_ds                = ws? ".ds" ws expression
    dot_include           = (symbol ":")? ws? ".include" ws string_literal
    dot_incchr            = ws? ".incchr" ws string_literal
    dot_org               = ws? ".org" ws symbol

    symbol_def            = macro_def / array_def / function_def / ram_var_def / local_var_def / dot_include / label_def / const_def

    macro_def             = macro_start (macro_body+ / if_clause) macro_end
    macro_start           = ws? symbol ":"? ws ".macro" comment? newline
    macro_body            = !macro_end ws? (dot_byte / dot_ds / macro_instruction_use) comment? newline
    macro_parameter       = "\\\\" dec_digit
    macro_instruction_use = (instruction ws macro_parameter) / instruction_use
    macro_end             = ws? (".endm" / ".ENDM")

    macro_use            = symbol ws expression_list

    if_clause             = if_start if_body+ if_end newline
    if_start              = ws? "if" ws (macro_parameter / literal) ws comparator ws (macro_parameter / literal) comment? newline
    comparator            = "<" / ">"
    if_body               = ws? "fail" everything newline
    if_end                = ws? "endif"

    function_def          = symbol ":"? ws ".func" ws expression
    ram_var_def           = repeating_symbols ws? symbol ":" ws ".ds" ws expression
    label_def             = ws? symbol ":" ws? (macro_use / instruction_use)?
    local_var_def         = ws? local_symbol ":" ws? everything
    const_def             = symbol ws? "=" ws? expression

    repeating_symbols     = ((ws? symbol ":" ws? comment? newline) / empty_line / comment_line)*

    array_def             = array_def_ml

    array_def_ml          = symbol ":" ws? (ws? comment? newline (ws? symbol ":")?)* (dot_byte_list / dot_word_list)
    dot_byte_list         = ws? dot_byte (newline (comment_line / empty_line)* ws? dot_byte)*
    dot_word_list         = ws? dot_word (newline (comment_line / empty_line)* ws? dot_word)*

    dot_word_line         = ws? dot_word newline
    dot_byte_line         = ws? dot_byte newline

    symbol                = global_symbol / local_symbol

    global_symbol         = ~"[A-Za-z_][A-Za-z0-9_]*"
    local_symbol          = "." global_symbol

    literal               = string_literal / number_literal

    string_literal        = ~r"\\".*?\\""
    number_literal        = negation? (hex_literal / bin_literal / dec_literal)

    negation              = "-"
    bit_negation          = "~"
    bin_literal           = "%" bin_digit+    
    dec_literal           = dec_digit+
    hex_literal           = "$" hex_digit+
    hex_digit             = ~"[0-9A-Fa-f]"
    dec_digit             = ~"[0-9]"
    bin_digit             = "0" / "1"

    function_call         = symbol "(" ws? expression_list ws? ")"

    expression            = negation? bit_negation? (paren_group / literal / macro_parameter / function_call / symbol) (ws operator ws expression)?
    operator              = "&" / "<<" / ">>" / "+" / "-" / "*" / "|" / "/"
    paren_group           = "(" expression ")"

    expression_list       = expression (ws? "," ws? expression)*
    """
)

if __name__ == "__main__":
    start = time()
    path = Path("/home/michael/Gits/smb3/smb3.asm")

    print(path)
    asm_grammar.parse(path.read_text())

    for i in range(32):
        path = Path(f"/home/michael/Gits/smb3/PRG/prg{i:0>3}.asm")
        print(path)
        asm_grammar.parse(path.read_text())

    print(time() - start)
