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
    const requestId = data.requestId ? ` (requestId: ${data.requestId})` : "";
    throw new Error(`${data.error || "Request failed"}${requestId}`);
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

async function loadServiceStatus() {
  try {
    const response = await fetch("/api/services");
    const data = await response.json();
    renderServiceStatus(data.services || []);
  } catch (error) {
    renderServiceStatus([
      { id: "portal", name: "Portal", status: "unreachable" }
    ]);
  }
}

function renderServiceStatus(services) {
  serviceStatus.innerHTML = "";
  const portalStatus = document.createElement("li");
  portalStatus.className = "status";
  portalStatus.innerHTML =
    "<span>Portal</span><span class=\"badge healthy\">healthy</span>";
  serviceStatus.appendChild(portalStatus);

  services.forEach((service) => {
    const item = document.createElement("li");
    item.className = "status";
    const badgeClass = service.status || "unconfigured";
    item.innerHTML = `
      <span>${service.name}</span>
      <span class="badge ${badgeClass}">${badgeClass}</span>
    `;
    serviceStatus.appendChild(item);
  });
}

generatePipelineButton.addEventListener("click", async () => {
  setPipelineStatus("Generating...");
  try {
    const data = await requestTemplate("/api/pipeline");
    latest.pipeline = data;
    updateOutput(pipelineOutput, data.content);
    setPipelineStatus(`Generated ${data.filename}`);
  } catch (error) {
    updateOutput(pipelineOutput, error.message);
    setPipelineStatus("Error");
  }
});

downloadPipelineButton.addEventListener("click", () => {
  downloadFile(latest.pipeline);
});

generateTerraformButton.addEventListener("click", async () => {
  try {
    const data = await requestTemplate("/api/terraform");
    latest.terraform = data;
    updateOutput(terraformOutput, data.content);
  } catch (error) {
    updateOutput(terraformOutput, error.message);
  }
});

downloadTerraformButton.addEventListener("click", () => {
  downloadFile(latest.terraform);
});

generateHelmButton.addEventListener("click", async () => {
  try {
    const data = await requestTemplate("/api/helm");
    latest.helm = data;
    updateOutput(helmOutput, data.content);
  } catch (error) {
    updateOutput(helmOutput, error.message);
  }
});

downloadHelmButton.addEventListener("click", () => {
  downloadFile(latest.helm);
});

loadIdentity().catch(() => { document.getElementById("identity").textContent = "Portal unavailable. Please reload."; });
setInterval(() => { if (profile) loadServiceStatus(); }, 10000);
