package com.portfolio.ecommerce.inventory;

import org.apache.kafka.common.TopicPartition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Configuration
public class KafkaErrorConfig {
  @Bean
  DefaultErrorHandler inventoryErrorHandler(KafkaTemplate<String, String> template) {
    DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(template,
        (record, exception) -> new TopicPartition(record.topic() + ".DLT", record.partition()));
    recoverer.setFailIfSendResultIsError(true);
    DefaultErrorHandler handler = new DefaultErrorHandler(recoverer, new FixedBackOff(200L, 2L));
    handler.addNotRetryableExceptions(IllegalArgumentException.class);
    return handler;
  }
}
