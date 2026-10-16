package com.portfolio.pipeline.flink;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class PredictionScorerTest {
  @Test
  void detectsUnseenAnomaliesWithTheFittedBaseline() {
    assertEquals(0, PredictionScorer.score(20, 5));
    assertTrue(PredictionScorer.score(21.5, 5) < 3);
    assertTrue(PredictionScorer.score(35, 5) > 3);
    assertEquals(PredictionScorer.score(5, 2), PredictionScorer.score(35, 200));
  }
  @Test void rejectsNonFiniteOrEmptyWindows() {
    assertThrows(IllegalArgumentException.class, () -> PredictionScorer.score(Double.NaN, 1));
    assertThrows(IllegalArgumentException.class, () -> PredictionScorer.score(Double.POSITIVE_INFINITY, 1));
    assertThrows(IllegalArgumentException.class, () -> PredictionScorer.score(20, 0));
  }
}
