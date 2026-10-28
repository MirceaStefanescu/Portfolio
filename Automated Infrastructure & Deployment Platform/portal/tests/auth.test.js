const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { createHash, randomUUID } = require("node:crypto");
const express = require("express");
const { generateKeyPair, exportJWK, SignJWT } = require("jose");
const { installAccess } = require("../src/auth");
let providerServer, portalServer, base, issuer, privateKey, jwk;
const codes = new Map();

before(async () => {
  const keys = await generateKeyPair("RS256"); privateKey = keys.privateKey;
  jwk = {...await exportJWK(keys.publicKey), kid: "fixture-key", alg: "RS256", use: "sig"};
  const provider = express(); provider.use(express.urlencoded({extended: false}));
  providerServer = provider.listen(0, "127.0.0.1"); await once(providerServer, "listening");
  issuer = "http://127.0.0.1:" + providerServer.address().port;
  provider.get("/.well-known/openid-configuration", (req, res) => res.json({issuer,
    authorization_endpoint: issuer + "/authorize", token_endpoint: issuer + "/token", jwks_uri: issuer + "/jwks",
    response_types_supported: ["code"], subject_types_supported: ["public"],
    id_token_signing_alg_values_supported: ["RS256"], code_challenge_methods_supported: ["S256"]}));
  provider.get("/jwks", (req, res) => res.json({keys: [jwk]}));
  provider.get("/authorize", (req, res) => {
    const code = randomUUID(); codes.set(code, req.query);
    const callback = new URL(req.query.redirect_uri);
    callback.searchParams.set("code", code); callback.searchParams.set("state", req.query.state);
    res.redirect(callback.href);
  });
  provider.post("/token", async (req, res) => {
    const request = codes.get(req.body.code); codes.delete(req.body.code);
    if (!request || req.body.client_secret !== "fixture-client-secret" || req.body.client_id !== "portal"
        || req.body.redirect_uri !== request.redirect_uri
        || createHash("sha256").update(req.body.code_verifier || "").digest("base64url") !== request.code_challenge) {
      return res.status(400).json({error: "invalid_grant"});
    }
    let token = await new SignJWT({nonce: request.bad_nonce ? "invalid" : request.nonce,
      name: "Test User", roles: [request.role || "portal-viewer"]})
      .setProtectedHeader({alg: "RS256", kid: "fixture-key"}).setIssuer(issuer)
      .setSubject("fixture-user").setAudience(request.bad_audience ? "another-app" : "portal")
      .setIssuedAt().setExpirationTime(request.expired ? "-1s" : "5m").sign(privateKey);
    if (request.bad_signature) { const parts = token.split("."); parts[2] = (parts[2][0] === "A" ? "B" : "A") + parts[2].slice(1); token = parts.join("."); }
    res.json({access_token: "fixture-access", token_type: "Bearer", expires_in: 300, id_token: token});
  });
  const portal = express(); portal.use(express.json());
  portalServer = portal.listen(0, "127.0.0.1"); await once(portalServer, "listening");
  base = "http://127.0.0.1:" + portalServer.address().port;
  installAccess(portal, {mode: "oidc", issuer, publicUrl: base, clientId: "portal", clientSecret: "fixture-client-secret",
    secret: "fixture-session-secret-of-more-than-32-bytes", localHttp: true});
  portal.get("/api/services", (req, res) => res.json({services: []}));
  portal.post("/api/pipeline", (req, res) => res.json({created: true}));
});
after(async () => {
  await Promise.all([providerServer, portalServer].map(server => new Promise(resolve => server?.close(resolve))));
});

const cookie = response => response.headers.getSetCookie().map(value => value.split(";")[0]).join("; ");
async function login(options = {}) {
  const start = await fetch(base + "/auth/login", {redirect: "manual"}); assert.equal(start.status, 302);
  const url = new URL(start.headers.get("location"));
  for (const [key, value] of Object.entries(options)) url.searchParams.set(key, value);
  const authorization = await fetch(url, {redirect: "manual"});
  const callback = new URL(authorization.headers.get("location"));
  if (options.bad_state) callback.searchParams.set("state", "wrong-state");
  return fetch(callback, {redirect: "manual", headers: {Cookie: cookie(start)}});
}
async function identity(session) {
  const response = await fetch(base + "/api/me", {headers: {Cookie: session}});
  assert.equal(response.status, 200); return response.json();
}
async function generate(session, csrf, environment) {
  return fetch(base + "/api/pipeline", {method: "POST", headers: {Cookie: session,
    "X-CSRF-Token": csrf, "Content-Type": "application/json"}, body: JSON.stringify({environment})});
}

test("OIDC denies anonymous access and validates signed identity with PKCE", async () => {
  assert.equal((await fetch(base + "/api/services")).status, 401);
  const callback = await login(); assert.equal(callback.status, 302);
  const session = cookie(callback), profile = await identity(session);
  assert.equal(profile.name, "Test User"); assert.equal(profile.role, "viewer");
  assert.equal((await generate(session, profile.csrf, "dev")).status, 403);
  assert.ok(callback.headers.getSetCookie().some(value => value.includes("HttpOnly") && value.includes("SameSite=Lax")));
});
test("developer can generate dev artifacts but requires CSRF and cannot target production", async () => {
  const session = cookie(await login({role: "portal-developer"})), profile = await identity(session);
  assert.equal((await generate(session, "invalid", "dev")).status, 403);
  assert.equal((await generate(session, profile.csrf, "dev")).status, 200);
  assert.equal((await generate(session, profile.csrf, "production")).status, 403);
});
test("admin access and logout are scoped to the verified encrypted session", async () => {
  const session = cookie(await login({role: "portal-admin"})), profile = await identity(session);
  assert.equal((await generate(session, profile.csrf, "prod")).status, 200);
  const modified = session.replace(/portal-session=./, "portal-session=!");
  assert.equal((await fetch(base + "/api/me", {headers: {Cookie: modified}})).status, 401);
  assert.equal((await fetch(base + "/api/logout", {method: "POST", headers: {Cookie: session}})).status, 403);
  const result = await fetch(base + "/api/logout", {method: "POST", headers: {Cookie: session, "X-CSRF-Token": profile.csrf}});
  assert.equal(result.status, 204); assert.ok(cookie(result).includes("portal-session="));
});
test("rejects wrong state, nonce, audience, expiry and signature", async () => {
  for (const failure of ["bad_state", "bad_nonce", "bad_audience", "expired", "bad_signature"]) {
    assert.equal((await login({[failure]: "true"})).status, 401, failure);
  }
});
test("does not silently fall back to demo or permit non-loopback HTTP", () => {
  assert.throws(() => installAccess(express(), {mode: "oidc"}), /required/);
  assert.throws(() => installAccess(express(), {mode: "oidc", issuer: "http://example.com", publicUrl: base,
    clientId: "portal", clientSecret: "secret", secret: "s".repeat(32), localHttp: true}), /HTTPS/);
});

test("OIDC rejects non-string environments before coercion and retains production restrictions", async () => {
  const session=cookie(await login({role:"portal-developer"})), profile=await identity(session);
  for(const environment of [{toString:null}, null, 12, [], ["prod"]]) {
    const response=await generate(session,profile.csrf,environment);
    assert.equal(response.status,400,JSON.stringify(environment));
  }
  assert.equal((await generate(session,profile.csrf," PRODUCTION ")).status,403);
  assert.equal((await generate(session,profile.csrf,"dev")).status,200);
});
