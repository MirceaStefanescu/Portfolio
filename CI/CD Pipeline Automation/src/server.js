require("dotenv").config();
const { createApp } = require("./app");

function startServer(port = process.env.PORT || 8080, { handleSignals = require.main === module } = {}) {
  const app = createApp();
  const server = app.listen(port, () => {
    console.log(`CI/CD demo app listening on port ${server.address().port}`);
  });

  if (handleSignals) {
    let timer;
    let stopping = false;
    const shutdown = () => {
      if (stopping) return;
      stopping = true;
      timer = setTimeout(() => process.exit(1), 10000);
      timer.unref();
      server.close((error) => { process.exitCode = error ? 1 : 0; });
    };
    process.once("SIGTERM", shutdown);
    process.once("SIGINT", shutdown);
    server.once("close", () => {
      clearTimeout(timer);
      process.removeListener("SIGTERM", shutdown);
      process.removeListener("SIGINT", shutdown);
    });
  }

  return { app, server };
}

if (require.main === module) startServer();
module.exports = { startServer };
