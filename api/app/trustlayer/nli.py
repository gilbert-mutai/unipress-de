"""DeBERTa NLI backend (Tier-1), multilingual (HU + EN) via mDeBERTa-XNLI.

Implements the `Entailment` port with real semantic entailment + contradiction
detection. transformers/torch are imported lazily and the model loads once per
process (like the embedder); selected via settings.nli_backend="nli". This is a
~560MB model download, so it stays opt-in (lexical proxy is the default).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.trustlayer.entailment import NLIScores

log = get_logger("trustlayer.nli")


class DebertaNLI:
    def __init__(self, model: str | None = None) -> None:
        from app.core.settings import get_settings

        self.model_name = model or get_settings().nli_model
        self._model: Any = None
        self._tok: Any = None
        self._id2label: dict[int, str] = {}

    def _load(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        log.info("nli.load", model=self.model_name)
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._model.eval()
        self._id2label = {i: str(v).lower() for i, v in self._model.config.id2label.items()}

    def classify(self, premise: str, hypothesis: str) -> NLIScores:
        import torch

        self._load()
        assert self._tok is not None and self._model is not None
        inputs = self._tok(
            premise, hypothesis, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.no_grad():
            probs = torch.softmax(self._model(**inputs).logits[0], dim=-1).tolist()

        scores = {"entail": 0.0, "neutral": 0.0, "contradict": 0.0}
        for i, p in enumerate(probs):
            label = self._id2label.get(i, "")
            if "entail" in label:
                scores["entail"] = p
            elif "contradict" in label:
                scores["contradict"] = p
            else:
                scores["neutral"] = p
        return NLIScores(**scores)

    def entail_prob(self, premise: str, hypothesis: str) -> float:
        return self.classify(premise, hypothesis).entail
