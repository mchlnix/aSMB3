from foundry.data_source.formula_parser import FormulaParser


def test_bit_or():
    fp = FormulaParser("OAT_BOUNDBOX01 | OAT_FIREIMMUNITY | OAT_HITNOTKILL")
    fp.parse()

    assert fp.parts == ["OAT_BOUNDBOX01", "|", "OAT_FIREIMMUNITY", "|", "OAT_HITNOTKILL"], fp.parts
    assert fp.debug_str_tree() == (
        "('', ROOT, l=["
        "('OAT_BOUNDBOX01', SYMBOL, l=[]), ('|', OPERATOR, l=[]), ('OAT_FIREIMMUNITY', SYMBOL, l=[]), "
        "('|', OPERATOR, l=[]), ('OAT_HITNOTKILL', SYMBOL, l=[])"
        "])"
    ), fp.debug_str_tree()


def test_number_listing():
    fp = FormulaParser("2,   4,   2,   8	; 0")
    fp.parse()

    assert fp.parts == ["2", "4", "2", "8"], fp.parts
    assert fp.debug_str_tree() == (
        (
            "('', ROOT, l=["
            "('', LISTING, l=[('2', NUMBER, l=[]), ('4', NUMBER, l=[]), ('2', NUMBER, l=[]), ('8', NUMBER, l=[])])"
            "])"
        )
    ), fp.debug_str_tree()


def test_function_call():
    fp = FormulaParser("MLEN(DMC01, DMC01_End)")
    fp.parse()

    assert fp.parts == ["MLEN", "DMC01", "DMC01_End"], fp.parts
    assert fp.debug_str_tree() == (
        "('', ROOT, l=["
        "('MLEN', FUNCTION_NAME, l=["
        "('()', FUNCTION_PARAMS, l=["
        "('', LISTING, l=[('DMC01', SYMBOL, l=[]), ('DMC01_End', SYMBOL, l=[])])"
        "])"
        "])"
        "])"
    ), fp.debug_str_tree()


def test_byte_listing():
    fp = FormulaParser("$00, -$03,  $03,  $00,  $00,  $00,  $00,  $00 ; $00-$07")
    fp.parse()

    assert fp.parts == "$00, -$03, $03, $00, $00, $00, $00, $00".split(", "), fp.parts
    assert fp.debug_str_tree() == (
        "('', ROOT, l=[('', LISTING, l=["
        "('$00', NUMBER, l=[]), ('-$03', NUMBER, l=[]), ('$03', NUMBER, l=[]), ('$00', NUMBER, l=[]), "
        "('$00', NUMBER, l=[]), ('$00', NUMBER, l=[]), ('$00', NUMBER, l=[]), ('$00', NUMBER, l=[])"
        "])])"
    ), fp.debug_str_tree()


def test_byte_listing_neg_at_start():
    fp = FormulaParser("-$01, $01")
    fp.parse()

    assert fp.parts == "-$01, $01".split(", "), fp.parts
    assert (
        fp.debug_str_tree() == "('', ROOT, l=[('', LISTING, l=[" "('-$01', NUMBER, l=[]), ('$01', NUMBER, l=[])" "])])"
    ), fp.debug_str_tree()


def test_paren_formula():
    fp = FormulaParser("(TimeBonus_Score - 1)")
    fp.parse()

    assert fp.parts == ["TimeBonus_Score", "-", "1"], fp.parts
    assert fp.debug_str_tree() == (
        "('', ROOT, l=["
        "('()', PARENS, l=[('TimeBonus_Score', SYMBOL, l=[]), ('-', OPERATOR, l=[]), ('1', NUMBER, l=[])])"
        "])"
    ), fp.debug_str_tree()


def test_paren_formula_in_listing():
    fp = FormulaParser("0, (LL_LargeBGClouds2B - LL_LargeBGClouds2)")
    fp.parse()

    assert fp.parts == ["0", "LL_LargeBGClouds2B", "-", "LL_LargeBGClouds2"], fp.parts
    assert fp.debug_str_tree() == (
        "('', ROOT, l=["
        "('', LISTING, l=["
        "('0', NUMBER, l=[]), ('()', PARENS, l=["
        "('LL_LargeBGClouds2B', SYMBOL, l=[]), ('-', OPERATOR, l=[]), ('LL_LargeBGClouds2', SYMBOL, l=[])"
        "])"
        "])"
        "])"
    ), fp.debug_str_tree()
