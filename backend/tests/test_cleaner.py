from app.services.resume.cleaner import clean_text


def test_collapses_repeated_spaces_and_tabs():
    assert clean_text("Python   \t  SQL") == "Python SQL"


def test_normalizes_line_endings():
    assert clean_text("a\r\nb\rc") == "a\nb\nc"


def test_limits_blank_lines_to_one():
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_replaces_non_breaking_space():
    assert clean_text("Jane\u00a0Doe") == "Jane Doe"


def test_removes_control_characters_but_keeps_newlines():
    assert clean_text("Jane\x00 Doe\x0c\nEngineer") == "Jane Doe\nEngineer"


def test_trims_spaces_around_newlines_and_ends():
    assert clean_text("  hello  \n  world  ") == "hello\nworld"


def test_empty_and_whitespace_only():
    assert clean_text("") == ""
    assert clean_text("  \n \t ") == ""


def test_keeps_bullets_and_unicode():
    assert clean_text("• Built café app") == "• Built café app"
