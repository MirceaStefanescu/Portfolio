const el = id => document.getElementById(id);
let orderId, timer, pendingKey;
async function api(path, method = "GET", data, headers = {}) {
  const response = await fetch("/api" + path, {method, headers: {"Content-Type": "application/json", ...headers}, body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || result.detail || ("Request failed: " + response.status));
  return result;
}
function show(id, data) { el(id).textContent = JSON.stringify(data, null, 2); }
async function action(work) {
  el("error").textContent = "";
  try { await work(); } catch (error) { el("error").textContent = error.message; }
}
async function refresh() {
  show("cart", await api("/carts/" + el("customer").value));
  show("inbox", await api("/notifications/" + el("customer").value));
}
async function poll() {
  const result = await api("/orders/" + orderId);
  show("order", result); await refresh();
  if (["DELIVERED", "COMPENSATED"].includes(result.status)) clearInterval(timer);
}
async function watchOrder() {
  clearInterval(timer);
  timer = setInterval(() => action(poll), 2000);
  await poll();
}
el("save").onclick = () => action(async () => {
  await api("/carts/" + el("customer").value, "PUT", {items: [{sku: el("product").value, quantity: Number(el("qty").value)}]});
  pendingKey = undefined; await refresh();
});
el("customer").onchange = () => action(async () => {
  clearInterval(timer); orderId = undefined; pendingKey = undefined; el("cancel").disabled = true;
  el("order").textContent = "No order selected."; await refresh();
});
el("checkout").onclick = () => action(async () => {
  el("checkout").disabled = true;
  try {
    pendingKey ||= crypto.randomUUID();
    const result = await api("/carts/" + el("customer").value + "/checkout", "POST",
      {scenario: el("scenario").value}, {"Idempotency-Key": pendingKey});
    orderId = result.orderId; el("cancel").disabled = false;
    await watchOrder();
  } finally { el("checkout").disabled = false; }
});
el("cancel").onclick = () => action(async () => { await api("/orders/" + orderId + "/cancel", "POST", {}); await watchOrder(); });
action(async () => {
  for (const p of await api("/catalog")) {
    const option = document.createElement("option"); option.value = p.sku;
    option.textContent = p.name + " · " + (p.priceCents / 100).toFixed(2) + " " + p.currency;
    el("product").append(option);
  }
  await refresh();
});
