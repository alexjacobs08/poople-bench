from poople_bench.cli import stratified_sample
from poople_bench.game import load_schedule


def test_stratified_sample():
    schedule = load_schedule()
    sample = stratified_sample(schedule, n=50, seed=42, max_index=374)
    assert len(sample) == 50
    assert len(set(sample)) == 50
    assert all(1 <= i <= 373 for i in sample)
    pars = {schedule[i].par for i in sample}
    assert any(p >= 8 for p in pars), "hard days must be represented"
    assert stratified_sample(schedule, n=50, seed=42, max_index=374) == sample
    assert sample == sorted(sample)
