package com.portfolio.pipeline.api.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.springframework.stereotype.Service;

@Service
public class PredictionSearchService {
  private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

  private final RestClient restClient;
  private final ObjectMapper objectMapper;

  public PredictionSearchService(RestClient restClient, ObjectMapper objectMapper) {
    this.restClient = restClient;
    this.objectMapper = objectMapper;
  }

  public Map<String, Object> search(String query, int limit) {
    int safeLimit = Math.min(Math.max(limit, 1), 200);
    Map<String, Object> match = new HashMap<>();
    match.put("event_type", query);

    Map<String, Object> queryBody = new HashMap<>();
    queryBody.put("match_phrase_prefix", match);

    Map<String, Object> payload = new HashMap<>();
    payload.put("size", safeLimit);
    payload.put("query", queryBody);

    try {
      Request request = new Request("GET", "/predictions/_search");
      request.addParameter("ignore_unavailable", "true");
      request.setJsonEntity(objectMapper.writeValueAsString(payload));
      Response response = restClient.performRequest(request);
      return objectMapper.readValue(response.getEntity().getContent(), MAP_TYPE);
    } catch (IOException e) {
      throw new IllegalStateException("Failed to query Elasticsearch", e);
    }
  }
}
