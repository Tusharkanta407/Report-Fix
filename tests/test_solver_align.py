from engine.ingestion import load_dataset
from engine.schemas import SolverResult
from engine.solver import align_final_answer_to_working


def test_align_scq_letter_to_working_number():
    ds = load_dataset("data")
    payload = ds.payloads["68e8734442c06737d6e56da4"]  # friction μ options
    solver = SolverResult(
        can_solve=True,
        final_answer="C",
        correct_options=["C"],
        working="F = 90 N\nμ * 100 = 80\nμ = 0.8.\nThe correct option is (C) 0.6.",
        confidence=0.95,
        missing_information=[],
        figure_required=False,
        observations=[],
    )
    fixed = align_final_answer_to_working(solver, payload)
    assert fixed.final_answer == "A"
    assert "aligned final_answer" in " ".join(fixed.observations)


def test_align_integer_to_working_number():
    ds = load_dataset("data")
    payload = ds.payloads["6263d75bdd44e265ef926d97"]  # buoyancy cube
    solver = SolverResult(
        can_solve=True,
        final_answer="10",
        correct_options=[],
        working="2a^2 = 800\na^2 = 400\na = 20 cm\nThus the side is 10 cm.",
        confidence=0.95,
        missing_information=[],
        figure_required=False,
        observations=[],
    )
    fixed = align_final_answer_to_working(solver, payload)
    assert fixed.final_answer == "20"
