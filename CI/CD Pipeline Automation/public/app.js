async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadStatus() {
  const [info, status] = await Promise.all([
    fetchJson("/api/info"),
    fetchJson("/api/status")
  ]);

  const values = [
    status?.environment, status?.releaseColor, status?.buildId,
    info?.build?.service, info?.build?.gitSha, info?.build?.startedAt
  ];
  if (!values.every((value) => typeof value === "string") ||
      !Array.isArray(info?.pipeline?.stages) ||
      !info.pipeline.stages.every((stage) => typeof stage === "string")) {
    throw new Error("Invalid deployment metadata");
  }

  document.getElementById("env").textContent = status.environment;
  document.getElementById("color").textContent = status.releaseColor;
  document.getElementById("build").textContent = status.buildId;

  document.getElementById("service").textContent = info.build.service;
  document.getElementById("sha").textContent = info.build.gitSha;
  document.getElementById("started").textContent = info.build.startedAt;

  const stages = document.getElementById("stages");
  stages.innerHTML = "";
  info.pipeline.stages.forEach((stage) => {
    const item = document.createElement("li");
    item.textContent = stage;
    stages.appendChild(item);
  });
}

loadStatus().catch((error) => {
  console.error(error);
  for (const id of ["env", "color", "build", "service", "sha", "started"]) {
    document.getElementById(id).textContent = "unavailable";
  }
  const stages = document.getElementById("stages");
  stages.innerHTML = "";
  const item = document.createElement("li");
  item.textContent = "unavailable";
  stages.appendChild(item);
});
