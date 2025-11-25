from enum import Enum

from rag_core import prompt


class IntentType(Enum):
    SYNONYM = ("synonym", prompt.synonym_prompt)
    DEFINITION = ("definition", prompt.definition_prompt)
    EXAMPLE = ("example", prompt.example_prompt)
    PRONUNCIATION = ("pronunciation", prompt.pronunciation_prompt)
    USAGE_GUIDANCE = ("usage_guidance", prompt.usage_prompt)
    ETYMOLOGY = ("etymology", prompt.etymology_prompt)
    WORD_FAMILY = ("word_family", prompt.general_prompt)

    def __init__(self, type_str: str, prompt_str: str):
        self.type = type_str
        self.prompt = prompt_str

    @classmethod
    def get_prompt_by_type(cls, type: str):
        for intent_type in IntentType:
            if intent_type.type == type:
                return intent_type.prompt
        return prompt.general_prompt


