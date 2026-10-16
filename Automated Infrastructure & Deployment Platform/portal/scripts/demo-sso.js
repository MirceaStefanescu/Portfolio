// Loopback-only identity provider for demonstrating the complete OIDC browser flow.
const express = require("express");
const http = require("node:http");
const { once } = require("node:events");
const { randomBytes, randomUUID, createHash } = require("node:crypto");
const { generateKeyPair, exportJWK, SignJWT } = require("jose");

async function listen(server, port) {
  server.listen(port, "127.0.0.1");
  await once(server, "listening");
  return "http://127.0.0.1:" + server.address().port;
}
function close(server) {
  server.closeAllConnections();
  return new Promise(resolve => server.close(resolve));
}

async function identityProvider({ port = 0, redirectUri, clientSecret }) {
  const keys = await generateKeyPair("RS256");
  const jwk = { ...await exportJWK(keys.publicKey), kid: "demo", alg: "RS256", use: "sig" };
  const app = express();
  app.use(express.urlencoded({ extended: false, limit: "8kb" }));
  app.use((req, res, next) => { res.set("Cache-Control", "no-store"); next(); });
  const server = http.createServer(app), issuer = await listen(server, port);
  const pending = new Map(), codes = new Map();
  function prune() {
    for (const collection of [pending, codes]) {
      for (const [id, value] of collection) if (value.expires < Date.now()) collection.delete(id);
    }
  }
  app.get("/.well-known/openid-configuration", (req, res) => res.json({ issuer,
    authorization_endpoint: issuer + "/authorize", token_endpoint: issuer + "/token",
    jwks_uri: issuer + "/jwks", response_types_supported: ["code"], subject_types_supported: ["public"],
    id_token_signing_alg_values_supported: ["RS256"], code_challenge_methods_supported: ["S256"] }));
  app.get("/jwks", (req, res) => res.json({ keys: [jwk] }));
  app.get("/authorize", (req, res) => {
    prune();
    const query = req.query;
    if (query.client_id !== "portal" || query.redirect_uri !== redirectUri ||
        query.response_type !== "code" || query.code_challenge_method !== "S256" ||
        typeof query.code_challenge !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(query.code_challenge) ||
        typeof query.state !== "string" || typeof query.nonce !== "string") {
      return res.status(400).json({ error: "invalid_request" });
    }
    if (pending.size >= 100) return res.sendStatus(429);
    const flow = randomUUID();
    pending.set(flow, { ...query, expires: Date.now() + 180000 });
    res.cookie("demo-consent", flow, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 180000 });
    res.type("html").send(`<!doctype html><html lang="en"><meta charset="utf-8"><title>Demo SSO</title>
      <style>body{max-width:650px;margin:4rem auto;font:18px system-ui}button,select{font:inherit;padding:.6rem}</style>
      <h1>Local demonstration identity provider</h1>
      <p>No external account is used. Choose a role to exercise the portal's access controls.</p>
      <form method="post" action="/authorize"><input type="hidden" name="flow" value="${flow}">
      <label>Demo role <select name="role"><option value="viewer">Viewer</option>
      <option value="developer">Developer</option><option value="admin">Administrator</option></select></label>
      <button type="submit">Sign in to the demo portal</button></form></html>`);
  });
  app.post("/authorize", (req, res) => {
    prune();
    const flow = req.body.flow, request = pending.get(flow);
    const cookie = (req.headers.cookie || "").split(";").some(value => value.trim() === "demo-consent=" + flow);
    if (req.headers.origin !== issuer || !cookie || !request ||
        !["viewer", "developer", "admin"].includes(req.body.role)) return res.sendStatus(400);
    if (codes.size >= 100) return res.sendStatus(429);
    pending.delete(flow);
    const code = randomUUID();
    codes.set(code, { ...request, role: req.body.role, expires: Date.now() + 60000 });
    const target = new URL(redirectUri);
    target.searchParams.set("state", request.state); target.searchParams.set("code", code);
    res.clearCookie("demo-consent", { path: "/" });
    res.redirect(target.href);
  });
  app.post("/token", async (req, res, next) => {
    try {
      prune();
      const request = codes.get(req.body.code); codes.delete(req.body.code);
      if (!request || req.body.grant_type !== "authorization_code" ||
          req.body.client_id !== "portal" || req.body.client_secret !== clientSecret ||
          req.body.redirect_uri !== redirectUri ||
          createHash("sha256").update(req.body.code_verifier || "").digest("base64url") !== request.code_challenge) {
        return res.status(400).json({ error: "invalid_grant" });
      }
      const token = await new SignJWT({ nonce: request.nonce, name: "Demo " + request.role,
        roles: ["portal-" + request.role] }).setProtectedHeader({ alg: "RS256", kid: "demo" })
        .setIssuer(issuer).setSubject("demo-" + request.role).setAudience("portal")
        .setIssuedAt().setExpirationTime("5m").sign(keys.privateKey);
      res.json({ id_token: token, access_token: randomBytes(24).toString("base64url"),
                 token_type: "Bearer", expires_in: 300 });
    } catch (error) { next(error); }
  });
  return { server, issuer };
}

async function startDemo({ portalPort = 8810, providerPort = 8811 } = {}) {
  const portal = http.createServer();
  const base = await listen(portal, portalPort);
  let provider;
  try {
    const clientSecret = randomBytes(32).toString("base64url");
    provider = await identityProvider({ port: providerPort, redirectUri: base + "/auth/callback", clientSecret });
    Object.assign(process.env, { PORTAL_AUTH_MODE: "oidc", OIDC_ISSUER: provider.issuer,
      OIDC_CLIENT_ID: "portal", OIDC_CLIENT_SECRET: clientSecret, PORTAL_PUBLIC_URL: base,
      PORTAL_SESSION_SECRET: randomBytes(40).toString("base64url"), OIDC_ALLOW_LOOPBACK_HTTP: "true" });
    portal.on("request", require("../src/server").app);
    return { base, issuer: provider.issuer, close: () => Promise.all([close(portal), close(provider.server)]) };
  } catch (error) {
    await close(portal);
    if (provider) await close(provider.server);
    throw error;
  }
}

if (require.main === module) {
  startDemo().then(demo => {
    console.log("Demonstration portal: " + demo.base + " — use Sign in and choose a role.");
    console.log("Local OIDC issuer: " + demo.issuer);
    for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, () => demo.close());
  }).catch(error => { console.error(error.message); process.exitCode = 1; });
}
module.exports = { startDemo, identityProvider };
