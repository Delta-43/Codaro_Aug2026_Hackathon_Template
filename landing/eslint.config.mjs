// Flat config, mirroring frontend/eslint.config.mjs — scoped to catching dead
// code (`no-unused-vars`) rather than enforcing style. See that file's header
// comment for the rationale; kept identical here deliberately.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

export default [
  { ignores: ["**/*", "!src/**"] },
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
];
