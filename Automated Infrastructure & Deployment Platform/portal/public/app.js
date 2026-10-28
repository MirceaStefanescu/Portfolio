const appNameInput = document.getElementById("appName");
const environmentInput = document.getElementById("environment");
const providerSelect = document.getElementById("provider");
const appCountInput = document.getElementById("appCount");

const pipelineOutput = document.getElementById("pipelineOutput");
const pipelineStatus = document.getElementById("pipelineStatus");
const terraformOutput = document.getElementById("terraformOutput");
const helmOutput = document.getElementById("helmOutput");
const serviceStatus = document.getElementById("serviceStatus");

const generatePipelineButton = document.getElementById("generatePipeline");
const downloadPipelineButton = document.getElementById("downloadPipeline");
const generateTerraformButton = document.getElementById("generateTerraform");
const downloadTerraformButton = document.getElementById("downloadTerraform");
const generateHelmButton = document.getElementById("generateHelm");
const downloadHelmButton = document.getElementById("downloadHelm");

const latest = {
  pipeline: null,
  terraform: null,
  helm: null
};
let profile = null;
async function loadIdentity() {
  const response = await fetch("/api/me");
  if (!response.ok) {
    document.getElementById("identity").textContent = "Sign in to access the portal.";
    document.getElementById("signIn").hidden = false;
    [generatePipelineButton, generateTerraformButton, generateHelmButton].forEach(button => button.disabled = true);
    return;
  }
  profile = await response.json();
  document.getElementById("identity").textContent = `${profile.name} · ${profile.role}${profile.mode === "demo" ? " · Local demonstration" : ""}`;
  document.getElementById("signOut").hidden = profile.mode === "demo";
  [generatePipelineButton, generateTerraformButton, generateHelmButton].forEach(button => button.disabled = profile.role === "viewer");
  await loadServiceStatus();
}
document.getElementById("signOut").addEventListener("click", async () => {
  const response = await fetch("/api/logout", {method: "POST", headers: {"X-CSRF-Token": profile?.csrf || ""}});
  if (response.ok) window.location.reload();
  else document.getElementById("identity").textContent = "Sign-out failed. Please retry.";
});

function buildPayload() {
  return {
    appName: appNameInput.value,
    environment: environmentInput.value,
    provider: providerSelect.value,
    appCount: Number(appCountInput.value)
  };
}

async function requestTemplate(endpoint) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": profile?.csrf || "" },
    body: JSON.stringify(buildPayload())
  });

  let data = {};
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }
  if (!response.ok) {
    const requestId = data?.requestId ? ` (requestId: ${data.requestId})` : "";
    throw new Error(`${data?.error || "Request failed"}${requestId}`);
  }

  if (!data || typeof data.filename !== "string" || !data.filename.trim() || typeof data.content !== "string") {
    throw new Error("Invalid artifact response");
  }

  return data;
}

function updateOutput(target, value) {
  target.textContent = value;
}

function setPipelineStatus(message) {
  pipelineStatus.textContent = message;
}

function downloadFile(entry) {
  if (!entry) {
    return;
  }
  const blob = new Blob([entry.content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = entry.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

let serviceStatusVersion = 0;
const serviceStates = new Set(["healthy", "unhealthy", "unconfigured", "unreachable"]);
async function loadServiceStatus() {
  const version = ++serviceStatusVersion;
  try {
    const response = await fetch("/api/services");
    if (!response.ok) throw new Error("Service status unavailable");
    const data = await response.json();
    if (!data || !Array.isArray(data.services) || data.services.some(service =>
      !service || typeof service.name !== "string" || !service.name.trim() || !serviceStates.has(service.status))) {
      throw new Error("Invalid service status response");
    }
    if (version !== serviceStatusVersion) return;
    renderServiceStatus([{name: "Portal", status: "healthy"}, ...data.services]);
  } catch (error) {
    if (version !== serviceStatusVersion) return;
    renderServiceStatus([{name: "Portal", status: "unreachable"}]);
  }
}

function renderServiceStatus(services) {
  serviceStatus.innerHTML = "";
  services.forEach((service) => {
    const item = document.createElement("li");
    item.className = "status";
    const name = document.createElement("span");
    name.textContent = service.name;
    const badge = document.createElement("span");
    badge.className = `badge ${service.status}`;
    badge.textContent = service.status;
    item.appendChild(name);
    item.appendChild(badge);
    serviceStatus.appendChild(item);
  });
}

const artifacts = {
  pipeline: {output: pipelineOutput, generate: generatePipelineButton, download: downloadPipelineButton, version: 0},
  terraform: {output: terraformOutput, generate: generateTerraformButton, download: downloadTerraformButton, version: 0},
  helm: {output: helmOutput, generate: generateHelmButton, download: downloadHelmButton, version: 0}
};

for (const [kind, artifact] of Object.entries(artifacts)) {
  artifact.generate.addEventListener("click", async () => {
    if (!profile || profile.role === "viewer") return;
    const version = ++artifact.version;
    latest[kind] = null;
    artifact.download.disabled = true;
    artifact.generate.disabled = true;
    updateOutput(artifact.output, "Generating...");
    if (kind === "pipeline") setPipelineStatus("Generating...");
    try {
      const data = await requestTemplate(`/api/${kind}`);
      if (version !== artifact.version) return;
      latest[kind] = data;
      updateOutput(artifact.output, data.content);
      artifact.download.disabled = false;
      if (kind === "pipeline") setPipelineStatus(`Generated ${data.filename}`);
    } catch (error) {
      if (version !== artifact.version) return;
      updateOutput(artifact.output, error.message);
      if (kind === "pipeline") setPipelineStatus("Error");
    } finally {
      if (version === artifact.version) artifact.generate.disabled = !profile || profile.role === "viewer";
    }
  });
  artifact.download.addEventListener("click", () => downloadFile(latest[kind]));
}

function invalidateArtifacts() {
  for (const [kind, artifact] of Object.entries(artifacts)) {
    // An older in-flight response must not restore a download for previous inputs.
    artifact.version++;
    latest[kind] = null;
    artifact.download.disabled = true;
    artifact.generate.disabled = !profile || profile.role === "viewer";
    updateOutput(artifact.output, "Inputs changed. Generate a new artifact.");
  }
  setPipelineStatus("Ready");
}
for (const input of [appNameInput, environmentInput, providerSelect, appCountInput]) {
  input.addEventListener("input", invalidateArtifacts);
  input.addEventListener("change", invalidateArtifacts);
}

loadIdentity().catch(() => { document.getElementById("identity").textContent = "Portal unavailable. Please reload."; });
setInterval(() => { if (profile) loadServiceStatus(); }, 10000);
