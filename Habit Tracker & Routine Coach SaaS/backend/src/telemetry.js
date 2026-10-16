function telemetry(endpoint) {
  if (!endpoint) return { middleware: (_req, _res, next) => next(), close: async () => {} };
  const { NodeTracerProvider, BatchSpanProcessor } = require("@opentelemetry/sdk-trace-node");
  const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-http");
  const { resourceFromAttributes } = require("@opentelemetry/resources");
  const provider = new NodeTracerProvider({ resource: resourceFromAttributes({ "service.name": "habit-coach-demo" }), spanProcessors: [new BatchSpanProcessor(new OTLPTraceExporter({ url: endpoint }),
    { maxQueueSize: 256, maxExportBatchSize: 32, scheduledDelayMillis: 1000, exportTimeoutMillis: 3000 })] });
  const tracer = provider.getTracer("habit-demo", "1.0.0");
  return { middleware: (req, res, next) => {
    const span = tracer.startSpan("HTTP " + req.method);
    res.once("finish", () => {
      // Route templates, never tokens, query strings or personal habit names.
      span.updateName(req.method + " " + (req.route?.path || "/unmatched"));
      span.setAttribute("http.response.status_code", res.statusCode);
      if (res.statusCode >= 500) span.setStatus({ code: 2 });
      span.end();
    });
    next();
  }, close: () => provider.shutdown() };
}
module.exports = { telemetry };
