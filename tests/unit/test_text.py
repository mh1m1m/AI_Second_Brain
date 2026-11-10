"""Oracle: the recorded outputs of the IR1.1 tokenizer probe (fts5_arabic_probe.output.json)."""
import pytest

from second_brain.text.normalise import NORMALISER_VERSION, normalise
from second_brain.text.stem import STEMMER_VERSION, light_stem, stem_text

RECORDED = {"محمد": ["محمد", "محمد"], "الكتاب": ["الكتاب", "كتاب"], "كتاب": ["كتاب", "كتاب"], "احمد": ["احمد", "احمد"], "أحمد": ["احمد", "احمد"],
            "المكتبة": ["المكتبه", "مكتب"], "مكتبة": ["مكتبه", "مكتب"], "مكتبات": ["مكتبات", "مكتب"], "مدرسة": ["مدرسه", "مدرس"], "مدرسه": ["مدرسه", "مدرس"],
            "مستشفى": ["مستشفي", "مستشف"], "2024": ["2024", "2024"], "٢٠٢٤": ["2024", "2024"], "library": ["library", "library"], "LIBRARY": ["library", "library"],
            "libraries": ["libraries", "libraries"], "لا": ["لا", "لا"]}


def test_versions_are_the_specified_ones():
    assert (NORMALISER_VERSION, STEMMER_VERSION) == ("ar-en-1", "ar-light-1")


@pytest.mark.parametrize("query", sorted(RECORDED))
def test_normaliser_and_stemmer_match_recorded_outputs(query):
    norm = normalise(query)
    assert [norm, light_stem(norm)] == RECORDED[query]


def test_diacritics_tatweel_and_presentation_forms():
    assert normalise("مُحَمَّدٌ") == "محمد"
    assert normalise("المـــكتبة") == "المكتبه"
    assert normalise("ﻟﻤﻜﺘﺒﺔ ﻻ") == "لمكتبه لا"


def test_direction_controls_are_removed():
    assert normalise("ab‮cd‏") == "abcd"


@pytest.mark.parametrize("text", ["قرأ مُحَمَّدٌ الكِتابَ", "The Library ٢٠٢٤", "", "ـــ", "أحمد وإبراهيم"])
def test_normaliser_is_idempotent(text):
    assert normalise(normalise(text)) == normalise(text)


def test_stem_text_matches_recorded_sentence():
    assert stem_text(normalise("وللمكتبات والكتب أهمية في المدارس")).split() == ["مكتب", "كتب", "اهم", "في", "مدارس"]


def test_non_arabic_tokens_are_untouched_and_stems_keep_three_letters():
    assert light_stem("libraries") == "libraries"
    assert light_stem("2024") == "2024"
    assert all(len(light_stem(normalise(w))) >= 3 for w in ["الكتاب", "مكتبات", "وللمكتبات", "مدرسة", "كتبها"])


def test_known_limitation_broken_plural_is_not_reduced():
    assert light_stem(normalise("مدارس")) != light_stem(normalise("مدرسة"))
