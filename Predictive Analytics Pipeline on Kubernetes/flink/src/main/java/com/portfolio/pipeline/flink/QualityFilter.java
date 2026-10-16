package com.portfolio.pipeline.flink;

import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.apache.flink.streaming.api.functions.ProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

/** Invalid input is observable and retained in a dead-letter topic. */
public class QualityFilter extends ProcessFunction<String, Event> {
  public static final OutputTag<String> REJECTED = new OutputTag<String>("rejected-events") {};
  private transient Counter accepted;
  private transient Counter rejected;
  @Override public void open(Configuration parameters) {
    accepted = getRuntimeContext().getMetricGroup().counter("qualityAccepted");
    rejected = getRuntimeContext().getMetricGroup().counter("qualityRejected");
  }
  @Override public void processElement(String input, Context context, Collector<Event> out) {
    Event event = EventParser.parse(input);
    if (event == null) {
      rejected.inc();
      context.output(REJECTED, input);
    } else {
      accepted.inc();
      out.collect(event);
    }
  }
}
