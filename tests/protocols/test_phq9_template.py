from app.protocols.loader import TemplateLoader


EXPECTED_OPTIONS = [
    (0, "Nenhuma vez"),
    (1, "Vários dias"),
    (2, "Mais da metade dos dias"),
    (3, "Quase todos os dias"),
]


def test_phq9_template_metadata_and_question_sequence() -> None:
    template = TemplateLoader().load("phq9")

    assert template.template_id == "phq9"
    assert template.version == "1.0"
    assert template.name == "PHQ-9"
    assert len(template.questions) == 9
    assert [question.id for question in template.questions] == [str(index) for index in range(1, 10)]


def test_phq9_questions_are_likert_with_expected_scale() -> None:
    template = TemplateLoader().load("phq9")

    for question in template.questions:
        assert question.type == "likert"
        assert [(option.value, option.label) for option in question.options] == EXPECTED_OPTIONS


def test_phq9_clinical_content_is_loaded_from_template() -> None:
    template = TemplateLoader().load("phq9")
    questions = {question.id: question.text for question in template.questions}

    assert questions["1"] == "Pouco interesse ou prazer em fazer as coisas"
    assert questions["2"] == "Sentir-se para baixo, deprimido(a) ou sem esperança"
    assert questions["9"] == "Pensamentos de que estaria melhor morto(a), ou de se ferir de alguma forma"


def test_phq9_skip_rule_is_declarative() -> None:
    template = TemplateLoader().load("phq9")

    assert len(template.skip_rules) == 1
    rule = template.skip_rules[0]
    assert rule.trigger.after_question == "2"
    assert rule.condition.operator == "sum"
    assert rule.condition.questions == ["1", "2"]
    assert rule.condition.comparison == "lt"
    assert rule.condition.value == 3
    assert rule.action == "end_block"
