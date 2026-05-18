from app.schemas.document import EvaluationTestCase


DEFAULT_EVALUATION_TESTSET = [
    EvaluationTestCase(
        question_id="q1",
        question="What evaluation methods are discussed?",
        expected_answer=(
            "The document discusses subjective listening tests, objective automatic metrics, "
            "task-based evaluation, contextual or interaction-based evaluation, benchmark-based "
            "evaluation, psychometric validation, and model-as-a-judge evaluation."
        ),
        expected_keywords=[
            "subjective listening tests",
            "objective automatic metrics",
            "task-based evaluation",
            "contextual",
            "benchmark",
            "psychometric",
            "model-as-a-judge",
        ],
    ),
    EvaluationTestCase(
        question_id="q2",
        question="Why is MOS alone not sufficient for TTS evaluation?",
        expected_answer=(
            "MOS alone is not sufficient because naturalness is vague, sentence-level quality "
            "does not capture long-form listening, and isolated utterance evaluation does not "
            "reflect dialogue or contextual interaction."
        ),
        expected_keywords=[
            "MOS",
            "naturalness",
            "vague",
            "long-form",
            "isolated utterances",
            "dialogue",
            "contextual",
        ],
    ),
    EvaluationTestCase(
        question_id="q3",
        question="Which evaluation dimensions should be used instead of only naturalness?",
        expected_answer=(
            "The document recommends dimensions such as intelligibility, pronunciation, "
            "naturalness, prosody appropriateness, expressiveness, listening effort, and overall preference."
        ),
        expected_keywords=[
            "intelligibility",
            "pronunciation",
            "naturalness",
            "prosody",
            "expressiveness",
            "listening effort",
            "overall preference",
        ],
    ),
    EvaluationTestCase(
        question_id="q4",
        question="How should a balanced prompt set for TTS evaluation be built?",
        expected_answer=(
            "A balanced prompt set should include simple declarative sentences, tutor-style explanations, "
            "questions, technical and academic terms, difficult pronunciations, longer passages, and "
            "contrastive or emphatic sentences."
        ),
        expected_keywords=[
            "simple declarative sentences",
            "tutor-style explanations",
            "interrogative",
            "technical",
            "difficult pronunciations",
            "longer passages",
            "contrastive",
        ],
    ),
    EvaluationTestCase(
        question_id="q5",
        question="What makes an application-specific benchmark useful for a voice-based tutor?",
        expected_answer=(
            "An application-specific benchmark is useful because it tests ordinary explanations, "
            "question asking, technical vocabulary, formulas, abbreviations, symbols, emotional emphasis, "
            "and longer explanations relevant to a tutor."
        ),
        expected_keywords=[
            "ordinary explanations",
            "question asking",
            "technical vocabulary",
            "formulas",
            "abbreviations",
            "symbols",
            "longer explanations",
        ],
    ),
]