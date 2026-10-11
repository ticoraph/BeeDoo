import numpy as np

from beedoo.voice.segmenter import UtteranceSegmenter

RATE = 1000
CHUNK = 100  # 0,1 s par morceau


def chunk(value: float = 0.0) -> np.ndarray:
    return np.full(CHUNK, value, dtype=np.float32)


def feed_all(segmenter, pattern):
    """pattern : liste de (nombre de morceaux, parole ?) ; retourne les phrases terminées."""
    out = []
    for count, speech in pattern:
        for _ in range(count):
            result = segmenter.feed(chunk(0.5 if speech else 0.0), speech)
            if result:
                out.append(result)
    return out


def test_silence_gives_nothing():
    assert feed_all(UtteranceSegmenter(RATE), [(100, False)]) == []


def test_sentence_is_returned_after_hangover_with_preroll():
    seg = UtteranceSegmenter(RATE, preroll=0.3, hangover=0.5, min_speech=0.3)
    result = feed_all(seg, [(10, False), (10, True), (10, False)])
    assert len(result) == 1
    # 0,3 s avant + 1,0 s de parole + 0,5 s de silence final
    assert abs(result[0].duration - 1.8) < 0.11
    assert result[0].audio[:300].max() == 0.0 and result[0].audio[300:1300].min() == 0.5


def test_short_noise_is_discarded():
    seg = UtteranceSegmenter(RATE, hangover=0.5, min_speech=0.3)
    assert feed_all(seg, [(1, True), (10, False)]) == []


def test_two_sentences_separated_by_silence():
    seg = UtteranceSegmenter(RATE, hangover=0.5)
    assert len(feed_all(seg, [(5, True), (8, False), (5, True), (8, False)])) == 2


def test_short_pause_inside_a_sentence_does_not_split_it():
    seg = UtteranceSegmenter(RATE, hangover=0.5)
    assert len(feed_all(seg, [(5, True), (3, False), (5, True), (8, False)])) == 1


def test_very_long_speech_is_cut():
    seg = UtteranceSegmenter(RATE, max_duration=2.0)
    assert len(feed_all(seg, [(50, True)])) >= 2
