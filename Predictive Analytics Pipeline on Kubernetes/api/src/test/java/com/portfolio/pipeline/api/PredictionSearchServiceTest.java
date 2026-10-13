package com.portfolio.pipeline.api;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.pipeline.api.service.PredictionSearchService;
import java.io.IOException;
import org.apache.http.entity.StringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class PredictionSearchServiceTest {
  final RestClient client = mock(RestClient.class);
  final ObjectMapper mapper = new ObjectMapper();
  final PredictionSearchService service = new PredictionSearchService(client, mapper);

  @Test void acceptsEmptyIndexResultsAndEncodesUserInputSafely() throws Exception {
    var response = mock(Response.class);
    when(response.getEntity()).thenReturn(new StringEntity("{\"hits\":{\"total\":{\"value\":0},\"hits\":[]}}"));
    when(client.performRequest(any())).thenReturn(response);
    assertTrue(service.search("sensor\"quoted", 500).containsKey("hits"));
    var request = ArgumentCaptor.forClass(Request.class);
    verify(client).performRequest(request.capture());
    assertEquals("true", request.getValue().getParameters().get("ignore_unavailable"));
    var payload = mapper.readTree(request.getValue().getEntity().getContent());
    assertEquals("sensor\"quoted", payload.at("/query/match_phrase_prefix/event_type").asText());
    assertEquals(200, payload.get("size").asInt());
  }

  @Test void doesNotDisguiseAnElasticsearchOutageAsAnEmptyIndex() throws Exception {
    when(client.performRequest(any())).thenThrow(new IOException("unavailable"));
    var error = assertThrows(IllegalStateException.class, () -> service.search("sensor", 5));
    assertInstanceOf(IOException.class, error.getCause());
  }
}
