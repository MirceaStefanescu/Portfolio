const { createHash, randomBytes } = require("node:crypto");
const oidc = require("openid-client");
const { EncryptJWT, jwtDecrypt } = require("jose");
const { rateLimit } = require("express-rate-limit");

const asyncRoute = handler => (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
const loopback = url => ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);

function settings(env = process.env) {
  return {mode: env.PORTAL_AUTH_MODE || "oidc", issuer: env.OIDC_ISSUER,
    clientId: env.OIDC_CLIENT_ID, clientSecret: env.OIDC_CLIENT_SECRET,
    secret: env.PORTAL_SESSION_SECRET, publicUrl: env.PORTAL_PUBLIC_URL,
    localHttp: env.OIDC_ALLOW_LOOPBACK_HTTP === "true"};
}

function installAccess(app, options = settings()) {
  if (options.mode === "demo") {
    app.get("/api/me", (req, res) => res.json({name: "Local demo", role: "admin", mode: "demo", csrf: ""}));
    app.use("/api", (req, res, next) => { req.actor = {sub: "local-demo", role: "admin"}; next(); });
    return;
  }
  if (options.mode !== "oidc" || !options.issuer || !options.clientId || !options.clientSecret
      || !options.publicUrl || Buffer.byteLength(options.secret || "") < 32) {
    throw new Error("OIDC issuer, client ID/secret, public URL and a session secret of at least 32 bytes are required; local demos must explicitly select PORTAL_AUTH_MODE=demo");
  }
  const issuer = new URL(options.issuer), publicUrl = new URL(options.publicUrl);
  const local = options.localHttp && loopback(issuer) && loopback(publicUrl);
  if ((!local && (issuer.protocol !== "https:" || publicUrl.protocol !== "https:"))
      || issuer.username || issuer.password || issuer.search || issuer.hash
      || publicUrl.username || publicUrl.password || publicUrl.pathname !== "/" || publicUrl.search || publicUrl.hash) {
    throw new Error("OIDC requires HTTPS and a canonical portal origin; HTTP is limited to explicitly configured loopback tests");
  }
  const key = createHash("sha256").update(options.secret).digest();
  const prefix = publicUrl.protocol === "https:" ? "__Host-portal-" : "portal-";
  const cookieOptions = {httpOnly: true, secure: publicUrl.protocol === "https:", sameSite: "lax", path: "/"};
  const authenticationLimit = rateLimit({windowMs: 10 * 60 * 1000, limit: 60,
    standardHeaders: "draft-8", legacyHeaders: false,
    message: {error: "Too many sign-in attempts; retry after the indicated delay"}});
  let discovery;
  function configuration() {
    if (!discovery) discovery = oidc.discovery(issuer, options.clientId,
      {client_secret: options.clientSecret, [oidc.clockTolerance]: 0}, undefined,
      {timeout: 10, execute: [oidc.enableNonRepudiationChecks, ...(local ? [oidc.allowInsecureRequests] : [])]})
      .catch(error => { discovery = undefined; throw error; });
    return discovery;
  }
  async function seal(value, purpose, seconds) {
    return new EncryptJWT(value).setProtectedHeader({alg: "dir", enc: "A256GCM"})
      .setIssuer("portfolio-portal").setAudience(purpose).setIssuedAt()
      .setExpirationTime(Math.floor(Date.now() / 1000) + seconds).encrypt(key);
  }
  async function read(req, purpose) {
    const value = (req.headers.cookie || "").split(";").map(item => item.trim())
      .find(item => item.startsWith(prefix + purpose + "="))?.slice((prefix + purpose + "=").length);
    if (!value || value.length > 4096) return null;
    try { return (await jwtDecrypt(value, key, {issuer: "portfolio-portal", audience: purpose,
      keyManagementAlgorithms: ["dir"], contentEncryptionAlgorithms: ["A256GCM"]})).payload; }
    catch { return null; }
  }
  app.get("/auth/login", authenticationLimit, asyncRoute(async (req, res) => {
    try {
      const config = await configuration();
      const verifier = oidc.randomPKCECodeVerifier(), state = oidc.randomState(), nonce = oidc.randomNonce();
      res.cookie(prefix + "flow", await seal({verifier, state, nonce}, "flow", 300), {...cookieOptions, maxAge: 300000});
      res.set("Cache-Control", "no-store");
      res.redirect(oidc.buildAuthorizationUrl(config, {scope: "openid profile", redirect_uri: publicUrl.origin + "/auth/callback",
        code_challenge: await oidc.calculatePKCECodeChallenge(verifier), code_challenge_method: "S256", state, nonce}).href);
    } catch { res.status(503).json({error: "Identity provider unavailable"}); }
  }));
  app.get("/auth/callback", authenticationLimit, asyncRoute(async (req, res) => {
    const flow = await read(req, "flow");
    res.clearCookie(prefix + "flow", cookieOptions);
    res.set("Cache-Control", "no-store");
    if (!flow) return res.status(401).json({error: "Login expired; start again"});
    try {
      const config = await configuration();
      const tokens = await oidc.authorizationCodeGrant(config, new URL(req.originalUrl, publicUrl), {
        pkceCodeVerifier: flow.verifier, expectedState: flow.state, expectedNonce: flow.nonce, idTokenExpected: true});
      const claims = tokens.claims();
      const roles = Array.isArray(claims.roles) ? claims.roles : [];
      const role = roles.includes("portal-admin") ? "admin" : roles.includes("portal-developer") ? "developer" : "viewer";
      const session = {sub: claims.sub, name: String(claims.name || claims.preferred_username || claims.sub).slice(0, 120),
        role, csrf: randomBytes(32).toString("base64url")};
      res.cookie(prefix + "session", await seal(session, "session", 3600), {...cookieOptions, maxAge: 3600000});
      res.redirect("/");
    } catch { res.status(401).json({error: "Identity verification failed; start again"}); }
  }));
  app.use("/api", asyncRoute(async (req, res, next) => {
    if (["/health", "/metrics"].includes(req.path)) return next();
    req.actor = await read(req, "session");
    res.set("Cache-Control", "no-store");
    if (!req.actor) return res.status(401).json({error: "Sign in required", login: "/auth/login"});
    if (!["GET", "HEAD", "OPTIONS"].includes(req.method)) {
      if (req.get("X-CSRF-Token") !== req.actor.csrf) return res.status(403).json({error: "Invalid CSRF token"});
      if (req.path !== "/logout" && !["developer", "admin"].includes(req.actor.role)) return res.status(403).json({error: "Developer access required"});
      if (req.path !== "/logout" && ["prod", "production"].includes(String(req.body?.environment || "").trim().toLowerCase())
          && req.actor.role !== "admin") return res.status(403).json({error: "Administrator access required for production"});
    }
    next();
  }));
  app.get("/api/me", (req, res) => res.json({name: req.actor.name, role: req.actor.role, csrf: req.actor.csrf, mode: "oidc"}));
  app.post("/api/logout", (req, res) => { res.clearCookie(prefix + "session", cookieOptions); res.sendStatus(204); });
}

module.exports = {installAccess, settings};
