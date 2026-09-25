import json

import httpx
import pytest

from poople_bench.choosers import JevJudge


def make_judge(answer, word_list=("hope", "pope", "poop"), batch_size=250):
    """A judge whose HTTP layer records every request and answers via `answer`."""
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": answer(body),
                                         "usage": {"input_tokens": 1000, "output_tokens": 50}})

    judge = JevJudge(api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler)),
                     word_list=list(word_list) if word_list is not None else None,
                     batch_size=batch_size)
    return judge, sent


def nouls(body):
    return {k: {"type": "noul", "noul": 0.9 if k == "hope" else 0.1} for k in body["questions"]}


def test_legality_asks_one_noul_per_string_and_returns_probabilities():
    judge, sent = make_judge(nouls)
    assert judge.legality(["hope", "hypp"]) == {"hope": 0.9, "hypp": 0.1}
    qs = sent[0]["questions"]
    assert set(qs) == {"hope", "hypp"}
    assert all(q["type"] == "noul" for q in qs.values())


def test_legality_never_mentions_the_goal():
    judge, sent = make_judge(nouls)
    judge.legality(["hope"])
    text = json.dumps(sent[0]).lower()
    assert "target" not in text and "ladder" not in text


def test_legality_reads_the_word_list_when_given_one():
    judge, sent = make_judge(nouls)
    judge.legality(["hope"])
    assert sent[0]["state"]["accepted_word_list"] == "hope poop pope"
    assert "`accepted_word_list`" in sent[0]["questions"]["hope"]["instructions"]


def test_legality_without_a_word_list_uses_the_models_own_vocabulary():
    judge, sent = make_judge(nouls, word_list=None)
    judge.legality(["hope"])
    assert "accepted_word_list" not in sent[0]["state"]
    assert "real English word" in sent[0]["questions"]["hope"]["instructions"]


def test_legality_splits_large_batches_across_requests():
    judge, sent = make_judge(nouls, batch_size=2)
    out = judge.legality(["aaaa", "bbbb", "cccc"])
    assert len(sent) == 2 and len(out) == 3


def test_closest_asks_one_choice_per_move_in_a_single_request():
    def answer(body):
        return {k: {"type": "choice", "choice": sorted(q["criteria"])[0],
                    "confidence": 0.5, "probabilities": {}} for k, q in body["questions"].items()}

    judge, sent = make_judge(answer)
    out = judge.closest({"p3=m": ["pomp", "tome"], "p4=s": ["pons", "oops"]})
    assert len(sent) == 1
    assert sent[0]["state"] == {"target_word": "poop"}
    assert out == {"p3=m": "pomp", "p4=s": "oops"}
    q = next(iter(sent[0]["questions"].values()))
    assert q["type"] == "choice" and set(q["criteria"]) <= {"pomp", "tome", "pons", "oops"}


def test_choose_sends_the_state_and_described_options_and_returns_the_answer():
    def answer(body):
        return {"next_change": {"type": "choice", "choice": "p3=m", "confidence": 0.82,
                                "probabilities": {"p3=m": 0.84, "p4=s": 0.16}}}

    judge, sent = make_judge(answer)
    state = {"current_word": "pope", "target_word": "poop"}
    criteria = {"p3=m": '"pope" becomes "pome".', "p4=s": '"pope" becomes "pops".'}
    choice, probs, conf = judge.choose(state, criteria)
    assert (choice, conf) == ("p3=m", 0.82) and probs["p3=m"] == 0.84
    assert sent[0]["state"] == state
    assert sent[0]["questions"]["next_change"]["criteria"] == criteria
    assert "`target_word`" in sent[0]["questions"]["next_change"]["instructions"]


def test_the_judge_counts_requests_tokens_and_cost():
    judge, _ = make_judge(nouls)
    judge.legality(["hope"])
    judge.legality(["pope"])
    assert judge.requests == 2
    assert judge.input_tokens == 2000
    assert judge.cost == pytest.approx(2000 / 1_000_000 * 0.042)
