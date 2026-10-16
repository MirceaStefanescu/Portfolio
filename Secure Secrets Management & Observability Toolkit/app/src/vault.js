const fs = require("fs");
const vault = require("node-vault");

function readFileTrim(filePath) {
  if (!filePath) {
    return "";
  }

  if (!fs.existsSync(filePath)) {
    return "";
  }

  return fs.readFileSync(filePath, "utf8").trim();
}

function loadAppRoleCredentials(roleIdFile, secretIdFile) {
  const roleId = process.env.VAULT_APPROLE_ROLE_ID || readFileTrim(roleIdFile);
  const secretId = process.env.VAULT_APPROLE_SECRET_ID || readFileTrim(secretIdFile);

  if (!roleId || !secretId) {
    throw new Error("Missing Vault AppRole credentials");
  }

  return { roleId, secretId };
}

function extractSecretData(response) {
  if (!response) {
    return {};
  }

  if (response.data && response.data.data) {
    return response.data.data;
  }

  if (response.data) {
    return response.data;
  }

  return response;
}

async function fetchVaultSecret({
  addr,
  secretPath,
  roleIdFile,
  secretIdFile
}) {
  const client = vault({ endpoint: addr, requestOptions: { timeout: 5000 } });
  const { roleId, secretId } = loadAppRoleCredentials(roleIdFile, secretIdFile);

  const login = await client.approleLogin({
    role_id: roleId,
    secret_id: secretId
  });

  client.token = login.auth.client_token;

  const secret = await client.read(secretPath);
  return extractSecretData(secret);
}

module.exports = {
  fetchVaultSecret
};
