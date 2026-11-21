from app.services.job.skills import appears_in_text, normalize_skill


# ---------- normalize_skill ----------

def test_lowercases_and_trims():
    assert normalize_skill("  Python  ") == "python"


def test_collapses_inner_whitespace():
    assert normalize_skill("machine   learning") == "machine learning"


def test_aliases_map_to_one_canonical_name():
    for written in ["JS", "js", "JavaScript", "ECMAScript"]:
        assert normalize_skill(written) == "javascript"


def test_react_variants():
    for written in ["React", "React.js", "ReactJS", "react js"]:
        assert normalize_skill(written) == "react"


def test_cloud_and_devops_aliases():
    assert normalize_skill("Amazon Web Services") == "aws"
    assert normalize_skill("K8s") == "kubernetes"
    assert normalize_skill("Google Cloud Platform") == "gcp"
    assert normalize_skill("CICD") == "ci/cd"


def test_rest_api_variants():
    assert normalize_skill("RESTful APIs") == "rest api"
    assert normalize_skill("REST APIs") == "rest api"


def test_unknown_skills_pass_through_lowercased():
    assert normalize_skill("Haskell") == "haskell"


def test_trailing_punctuation_is_removed():
    assert normalize_skill("Python.") == "python"
    assert normalize_skill("(SQL)") == "sql"


def test_leading_dot_in_dotnet_is_kept():
    assert normalize_skill(".NET") == ".net"
    assert normalize_skill("dotnet") == ".net"


def test_inner_dots_are_kept():
    assert normalize_skill("Node.js") == "node.js"
    assert normalize_skill("NodeJS") == "node.js"


def test_special_character_skills():
    assert normalize_skill("C++") == "c++"
    assert normalize_skill("C#") == "c#"


def test_blank_becomes_empty_string():
    assert normalize_skill("   ") == ""


# ---------- appears_in_text (text is expected to be lowercase) ----------

def test_finds_whole_word():
    assert appears_in_text("docker", "deployed services with docker and compose")


def test_sql_does_not_match_inside_mysql():
    assert not appears_in_text("sql", "administered a mysql database")


def test_java_does_not_match_inside_javascript():
    assert not appears_in_text("java", "wrote javascript for the frontend")


def test_java_matches_when_it_is_its_own_word():
    assert appears_in_text("java", "migrated a legacy java service")


def test_matches_at_end_of_sentence():
    assert appears_in_text("python", "i mostly write python.")


def test_matches_hyphenated_phrase():
    assert appears_in_text("python", "built python-based tooling")


def test_finds_skill_through_an_alias_form():
    # canonical is "kubernetes", but the text says "k8s"
    assert appears_in_text("kubernetes", "managed k8s clusters in production")


def test_finds_multiword_skill():
    assert appears_in_text("machine learning", "applied machine learning to churn data")


def test_cpp_is_found():
    assert appears_in_text("c++", "wrote performance-critical c++ code")


def test_very_short_skills_are_never_searched_in_text():
    assert not appears_in_text("go", "ready to go to market quickly")
    assert not appears_in_text("c", "plan c was approved")


def test_missing_skill_is_not_found():
    assert not appears_in_text("kubernetes", "deployed with docker")
