"""Skill normalization and text search - plain Python, no AI.

Problem: "JS", "JavaScript" and "javascript" are the same skill, but a naive string
comparison treats them as different. Solution: reduce every skill name to ONE canonical
form before comparing. The table below is deliberately small and easy to extend: when you
notice a mismatch in real use, add a line.
"""

import re

# alias (lowercase)  ->  canonical name (lowercase)
ALIASES: dict[str, str] = {
    "js": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "angularjs": "angular",
    "angular.js": "angular",
    "nextjs": "next.js",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "ml": "machine learning",
    "natural language processing": "nlp",
    "restful": "rest api",
    "restful api": "rest api",
    "restful apis": "rest api",
    "rest apis": "rest api",
    "golang": "go",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "dotnet": ".net",
    "cpp": "c++",
    "c plus plus": "c++",
    "csharp": "c#",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
}

# Reverse index: canonical name -> every way it might be written in free text.
_FORMS: dict[str, set[str]] = {}
for _alias, _canonical in ALIASES.items():
    _FORMS.setdefault(_canonical, {_canonical}).add(_alias)


def normalize_skill(name: str) -> str:
    """Reduce a skill name to its canonical lowercase form ('React.js ' -> 'react')."""
    text = re.sub(r"\s+", " ", name.strip().lower())
    # Trim surrounding punctuation, but keep a LEADING dot (".net") and inner dots ("node.js").
    text = text.strip(" ,;:()[]").rstrip(".")
    return ALIASES.get(text, text)


def appears_in_text(canonical_skill: str, text: str) -> bool:
    """True if the skill is mentioned as a whole word/phrase in `text` (already lowercase).

    Whole-word matching matters: "sql" must NOT match inside "mysql", and "java" must
    NOT match inside "javascript". Very short names (1-2 characters, like "go", "c", "r")
    are never searched for in free text because they are too ambiguous ("go to market").
    """
    if len(canonical_skill) <= 2:
        return False

    for form in _FORMS.get(canonical_skill, {canonical_skill}):
        if len(form) <= 2:
            continue
        # The character before and after must not continue a word (letters, digits, + or #).
        pattern = rf"(?<![a-z0-9+#.]){re.escape(form)}(?![a-z0-9+#])"
        if re.search(pattern, text):
            return True
    return False
