const { test } = require("node:test");
const assert = require("node:assert/strict");
const { startDemo } = require("../scripts/demo-sso");
const cookies = response => response.headers.getSetCookie().map(value => value.split(";")[0]).join("; ");

test("interactive local SSO completes consent, signed callback and authorized generation", async () => {
  const demo = await startDemo({ portalPort: 0, providerPort: 0 });
  try {
    assert.equal((await fetch(demo.base + "/api/me")).status, 401);
    const start = await fetch(demo.base + "/auth/login", { redirect: "manual" });
    const consent = await fetch(start.headers.get("location"));
    assert.equal(consent.status, 200);
    const html = await consent.text();
    assert.match(html, /Local demonstration identity provider/);
    const flow = html.match(/name="flow" value="([^"]+)"/)[1];
    const body = new URLSearchParams({ flow, role: "developer" });
    const options = { method: "POST", redirect: "manual", body,
      headers: { Cookie: cookies(consent), Origin: demo.issuer } };
    const authorized = await fetch(demo.issuer + "/authorize", options);
    assert.equal(authorized.status, 302);
    assert.equal((await fetch(demo.issuer + "/authorize", options)).status, 400, "consent is single use");
    const callback = await fetch(authorized.headers.get("location"),
      { redirect: "manual", headers: { Cookie: cookies(start) } });
    assert.equal(callback.status, 302);
    const session = cookies(callback);
    const identity = await (await fetch(demo.base + "/api/me", { headers: { Cookie: session } })).json();
    assert.equal(identity.role, "developer");
    const generated = await fetch(demo.base + "/api/pipeline", { method: "POST",
      headers: { Cookie: session, "X-CSRF-Token": identity.csrf, "Content-Type": "application/json" },
      body: JSON.stringify({ appName: "demo-store", environment: "dev", provider: "github" }) });
    assert.equal(generated.status, 200);
    assert.match((await generated.json()).content, /demo-store/);
  } finally { await demo.close(); }
});
