package com.portfolio.pipeline.api.controller;

import com.portfolio.pipeline.api.model.EventRequest;
import com.portfolio.pipeline.api.model.PredictionResponse;
import com.portfolio.pipeline.api.service.EventProducer;
import com.portfolio.pipeline.api.service.PredictionQueryService;
import com.portfolio.pipeline.api.service.PredictionSearchService;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class AnalyticsController {
  private final EventProducer eventProducer;
  private final PredictionQueryService predictionQueryService;
  private final PredictionSearchService predictionSearchService;

  public AnalyticsController(
      EventProducer eventProducer,
      PredictionQueryService predictionQueryService,
      PredictionSearchService predictionSearchService
  ) {
    this.eventProducer = eventProducer;
    this.predictionQueryService = predictionQueryService;
    this.predictionSearchService = predictionSearchService;
  }

  @PostMapping("/events")
  public CompletableFuture<ResponseEntity<Void>> publishEvent(@RequestBody EventRequest request) {
    return eventProducer.publish(request).thenApply(ignored -> ResponseEntity.accepted().build());
  }

  @GetMapping("/predictions")
  public List<PredictionResponse> listPredictions(
      @RequestParam(name = "eventType", required = false) String eventType,
      @RequestParam(name = "limit", defaultValue = "20") int limit
  ) {
    return predictionQueryService.fetchPredictions(eventType, limit);
  }

  @GetMapping("/predictions/search")
  public Map<String, Object> searchPredictions(
      @RequestParam(name = "q") String q,
      @RequestParam(name = "limit", defaultValue = "20") int limit
  ) {
    return predictionSearchService.search(q, limit);
  }

  @GetMapping("/health")
  public Map<String, String> health() {
    return Map.of("status", "ok");
  }

  @ExceptionHandler(IllegalArgumentException.class)
  public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException ex) {
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(Map.of("error", ex.getMessage()));
  }
}
