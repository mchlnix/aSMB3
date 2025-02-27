from pathlib import Path

from parsimonious.grammar import Grammar

asm_grammar = Grammar(
    """
    instruction_use = instruction ws hexadecimal
    instruction     = "ADC" / "AND" / "ASL" / "BCC" / "BCS" / "BEQ" / "BIT" / "BMI" / "BNE" / "BPL" / "BRA" / "BRK" / "BVC" / "BVS" / "CLC" / "CLD" / "CLI" / "CLV" / "CMP" / "CPX" / "CPY" / "DEC" / "DEX" / "DEY" / "EOR" / "INC" / "INX" / "INY" / "JMP" / "JSR" / "LDA" / "LDX" / "LDY" / "LSR" / "NOP" / "ORA" / "PHA" / "PHP" / "PLA" / "PLP" / "ROL" / "ROR" / "RTI" / "RTS" / "SBC" / "SEC" / "SED" / "SEI" / "STA" / "STX" / "STY" / "TAX" / "TAY" / "TSX" / "TXA" / "TXS" / "TYA"
    directive       = ".LIST" / ".NOLIST" / ".MLIST" / ".NOMLIST" / ".OPT" / ".EQU" / ".BANK" / ".ORG" / ".DB" / ".DW" / ".BYTE" / ".WORD" / ".DS" / ".RSSET" / ".RS" / ".MACRO" / ".ENDM" / ".PROC" / ".ENDP" / ".PROCGROUP" / ".ENDPROCGROUP" / ".INCBIN" / ".INCLUDE" / ".INCCHR" / ".DEFCHR" / ".ZP" / ".BSS" / ".CODE" / ".DATA" / ".IF" / ".IFDEF" / ".IFNDEF" / ".ELSE" / ".ENDIF" / ".FAIL" / ".INESPRG" / ".INESCHR" / ".INESMAP" / ".INESMIR"
    hexadecimal     = ~r"\$[0-9]+"
    decimal         = !"$"!"%" ~r"[0-9]+"
    ws              = ~r"\s*"
    """
)

path = Path("/home/michael/Gits/smb3/smb3.asm")

# asm_grammar.parse(path.read_text(), 0)
result = asm_grammar.parse("ADC $01", 0)

print(result)
