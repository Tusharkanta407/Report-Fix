from engine.ingestion import answer_malformation, format_like_stored, normalize_answer


def test_mcq_comma_string_in_list_normalizes_to_letters():
    assert normalize_answer(["A, B, D"], "mcq") == "A,B,D"


def test_mcq_empty_entry_is_ignored_for_compare_but_flagged():
    assert normalize_answer(["", "B"], "mcq") == "B"
    assert "empty entries" in answer_malformation(["", "B"], "mcq")


def test_scq_variants():
    assert normalize_answer("c", "scq") == "C"
    assert normalize_answer("(C)", "scq") == "C"
    assert normalize_answer("Option D", "scq") == "D"


def test_integer_canonical_forms():
    assert normalize_answer("8", "integerQuestion") == "8"
    assert normalize_answer("8.0", "integerQuestion") == "8"
    assert normalize_answer(" 3113 ", "integerQuestion") == "3113"
    assert normalize_answer("0.080", "integerQuestion") == "0.08"
    assert normalize_answer("n = 1", "integerQuestion") == "1"


def test_format_like_stored_preserves_shape():
    assert format_like_stored(["A, B, D"], "A,B") == ["A, B"]
    assert format_like_stored("C", "A") == "A"


def test_wellformed_answers_not_flagged():
    assert answer_malformation("C", "scq") is None
    assert answer_malformation("3113", "integerQuestion") is None
    assert answer_malformation(["A, B, D"], "mcq") is None
