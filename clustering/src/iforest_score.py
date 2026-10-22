"""
Cham anomaly score bang Isolation Forest - lop TUY CHON thay cong thuc
z-score trong anomaly_score.py khi duoc bat.

MAC DINH TAT (CLUSTERING_SCORER=zscore). Bat: CLUSTERING_SCORER=iforest.
Chi can scikit-learn (khong can sentence-transformers/torch).

Ba quyet dinh thiet ke dang luu y:

1. MOT model dung chung cho TAT CA cum trong moi lan chay (pooled), khong
   phai 1 model/cum: moi cum chi co CLUSTERING_BASELINE_WINDOWS diem lich su
   (mac dinh 6) - qua it de Isolation Forest hoc duoc gi. Gop lich su cua moi
   cum lai thi du lieu du de model biet "muc do loi binh thuong" trong he
   thong trong nhu the nao.

2. Feature moi diem la [count, count_cua_bucket_truoc, chenh_lech]: Isolation
   Forest nhin duoc ca MUC DO lan TOC DO THAY DOI, khac z-score chi nhin
   duoc mot chieu (count so voi mean/stdev).

3. Dau ra duoc dua ve CUNG THANG DO voi z-score: lay z-score cua "do bi co
   lap" (score_samples) cua diem hien tai so voi phan bo do bi co lap cua
   lich su. Nho vay ANOMALY_THRESHOLD=2.0 giu nguyen y nghia "lech khoang 2
   do lech chuan so voi binh thuong" - khong phai chinh lai nguong, khong
   lam vo evidence precision/recall da co, va alert.py khong can sua gi.

QUAN TRONG - vi sao score cuoi cung la max(z-score, iforest) (xem combine()):
score_samples() cua Isolation Forest co mien gia tri BI CHAN (xap xi
[-0.5, 0]), nen moi diem cuc doan deu bi dong ve gan mot gia tri nho nhat.
Da do thuc te: mot burst 200 loi tren lich su ~2 loi/bucket chi ra score
1.833 - DUOI nguong 2.0, tuc neu dung iforest mot minh thi burst lon lai
KHONG alert, kem nhay hon chinh z-score. Vi vay iforest chi duoc dung de
LAM TANG score (bat them cac bat thuong ve toc do thay doi ma z-score mot
chieu bo sot), khong bao gio lam giam: bat lop ML len khong the khien he
thong phat hien te hon luong rule-based.

Moi tinh huong khong du du lieu / thieu scikit-learn / loi bat ky deu tra
None de main.py dung lai z-score (fallback rule-based).
"""

from __future__ import annotations

import os
from statistics import fmean, pstdev
from typing import Sequence

# Duoi nguong nay thi Isolation Forest chi hoc duoc nhieu -> tra None, dung z-score.
MIN_POOLED_SAMPLES = int(os.environ.get("CLUSTERING_IFOREST_MIN_SAMPLES", "10"))
RANDOM_STATE = int(os.environ.get("CLUSTERING_IFOREST_SEED", "0"))


def _enabled() -> bool:
    return os.environ.get("CLUSTERING_SCORER", "zscore").strip().lower() == "iforest"


def history_features(counts: Sequence[int]) -> list[list[float]]:
    """Diem huan luyen tu lich su: moi bucket ghep voi bucket ngay truoc no.

    `counts` theo dung thu tu cua baseline.historical_bucket_counts():
    index 0 la bucket gan hien tai nhat, index tang dan la lui ve qua khu.
    """
    return [
        [float(counts[i]), float(counts[i + 1]), float(counts[i] - counts[i + 1])]
        for i in range(len(counts) - 1)
    ]


def current_features(counts: Sequence[int], current_count: int) -> list[float] | None:
    if not counts:
        return None
    return [float(current_count), float(counts[0]), float(current_count - counts[0])]


class IsolationForestScorer:
    """Model da fit + phan bo do-bi-co-lap cua lich su de quy ve thang z-score."""

    def __init__(self, model, reference_mean: float, reference_stdev: float) -> None:
        self._model = model
        self._mean = reference_mean
        self._stdev = reference_stdev

    def score(self, counts: Sequence[int], current_count: int) -> float | None:
        """Score >= 0 tren cung thang do voi z-score; None = khong cham duoc."""
        features = current_features(counts, current_count)
        if features is None:
            return None
        try:
            isolation = float(self._model.score_samples([features])[0])
        except Exception:
            return None
        # score_samples: cang CAO cang binh thuong -> dao dau de score cang
        # cao cang bat thuong, giong huong cua z-score.
        return round(max(0.0, (self._mean - isolation) / self._stdev), 3)


def fit_scorer(counts_by_key: dict, *, min_samples: int | None = None) -> IsolationForestScorer | None:
    """Fit mot Isolation Forest tu lich su gop cua tat ca cum trong lan chay nay.

    Tra ve None khi khong kha thi (thieu scikit-learn, qua it du lieu, lich su
    phang tuyet doi) - khi do main.py dung z-score.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return None

    samples: list[list[float]] = []
    for counts in counts_by_key.values():
        samples.extend(history_features(counts))

    threshold = MIN_POOLED_SAMPLES if min_samples is None else min_samples
    if len(samples) < threshold:
        return None

    try:
        # random_state co dinh: cung du lieu vao phai ra cung score o moi lan
        # chay, neu khong score se nhay giua cac chu ky du khong co gi doi.
        model = IsolationForest(random_state=RANDOM_STATE).fit(samples)
        reference = [float(value) for value in model.score_samples(samples)]
    except Exception:
        return None

    stdev = pstdev(reference) if len(reference) > 1 else 0.0
    if stdev <= 0:  # lich su phang -> khong co thang do de so sanh
        return None
    return IsolationForestScorer(model, fmean(reference), stdev)


def combine(zscore: float, ml_score: float | None) -> float:
    """Score cuoi cung = max(z-score, iforest). Xem docstring dau file ve
    ly do khong dung iforest mot minh."""
    if ml_score is None:
        return zscore
    return max(zscore, ml_score)


def maybe_fit_scorer(counts_by_key: dict) -> IsolationForestScorer | None:
    """Diem duy nhat main.py goi: tra None khi tat hoac khong kha thi."""
    if not _enabled() or not counts_by_key:
        return None
    try:
        return fit_scorer(counts_by_key)
    except Exception as exc:  # job nen: khong duoc sap vi lop tuy chon nay
        print(f"[clustering] iforest bi bo qua, dung z-score: {type(exc).__name__}: {exc}")
        return None
