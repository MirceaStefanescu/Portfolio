const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
  { ignores: [".devtools/**", "node_modules/**", "coverage/**"] },
  {
    files: ["src/**/*.js", "tests/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "commonjs", globals: globals.node },
    rules: { ...js.configs.recommended.rules, "no-unused-vars": ["error", { argsIgnorePattern: "^_" }] }
  }
];
