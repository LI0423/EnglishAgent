from typing import Optional


_LISTENING_ERROR_BY_QTYPE = {
    "multiple_choice": "listening_option_misjudge",
    "form_fill": "listening_spelling_or_form_error",
    "note_completion": "listening_keyword_capture_miss",
    "map_labeling": "listening_location_mapping_error",
    "matching": "listening_matching_mismatch",
}

_READING_ERROR_BY_QTYPE = {
    "tfng": "reading_tfng_misjudge",
    "heading_matching": "reading_heading_mismatch",
    "attitude": "reading_attitude_misjudge",
    "inference": "reading_inference_error",
    "matching": "reading_matching_mismatch",
    "summary_completion": "reading_summary_fill_error",
}

_SPEAKING_ERROR_BY_DIM = {
    "fc": "speaking_fluency_coherence_low",
    "lr": "speaking_lexical_resource_low",
    "gr": "speaking_grammar_range_accuracy_low",
    "pr": "speaking_pronunciation_low",
}

_WRITING_ERROR_BY_CATEGORY = {
    "structure": "writing_structure_issue",
    "content": "writing_content_issue",
    "vocabulary": "writing_vocabulary_issue",
    "grammar": "writing_grammar_issue",
}

_WRITING_ERROR_BY_DIM = {
    "structure": "writing_structure_low_band",
    "content": "writing_content_low_band",
    "vocabulary": "writing_vocabulary_low_band",
    "grammar": "writing_grammar_low_band",
}


def normalize_listening_error_type(question_type: Optional[str]) -> str:
    qtype = str(question_type or "").strip().lower()
    return _LISTENING_ERROR_BY_QTYPE.get(qtype, "listening_content_miss")


def normalize_reading_error_type(question_type: Optional[str]) -> str:
    qtype = str(question_type or "").strip().lower()
    return _READING_ERROR_BY_QTYPE.get(qtype, "reading_content_miss")


def normalize_speaking_error_type(dim: Optional[str]) -> str:
    key = str(dim or "").strip().lower()
    return _SPEAKING_ERROR_BY_DIM.get(key, "speaking_general_low_band")


def normalize_writing_feedback_error_type(category: Optional[str]) -> str:
    key = str(category or "").strip().lower()
    return _WRITING_ERROR_BY_CATEGORY.get(key, "writing_general_issue")


def normalize_writing_dim_error_type(dim: Optional[str]) -> str:
    key = str(dim or "").strip().lower()
    return _WRITING_ERROR_BY_DIM.get(key, "writing_general_low_band")
