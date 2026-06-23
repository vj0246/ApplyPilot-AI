const nextConfig = require("eslint-config-next/core-web-vitals");
const tsPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = [
  ...nextConfig,
  {
    plugins: { "@typescript-eslint": tsPlugin },
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "off",
      "react/no-unescaped-entities": "off",
      "@next/next/no-img-element": "off",
    },
  },
];
