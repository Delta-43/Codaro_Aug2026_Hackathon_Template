// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

// Flat config. Like the ruff config on the backend, this is scoped to catching
// dead code rather than enforcing a style — `no-unused-vars` is the rule that
// pays for this file's existence. Next's own configs come along because
// disabling its correctness rules to add one of ours would be a bad trade.
//
// eslint-config-next exports native flat arrays, so no FlatCompat wrapper.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

export default [
  // Allowlist, not a denylist: lint src/ and nothing else. `eslint .` would
  // otherwise walk the whole frontend/ tree, so any unignored directory that
  // lands here (build output, a vendored copy, a scratch dir) fails the lint
  // gate for code that is not the app. Enumerating dirs to ignore cannot cover
  // the ones nobody has created yet, so ignore everything and re-include src/.
  { ignores: ["**/*", "!src/**"] },
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        // Underscore-prefixed names are the escape hatch for a binding that has
        // to exist (positional args, destructuring rest) but is not read.
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

      // eslint-config-next@16 ships React-19-compiler-era rules. This app is on
      // React 18, and acting on these means changing runtime behaviour — out of
      // scope for a dead-code pass. Kept as warnings so they stay visible and
      // can be worked through deliberately, rather than switched off and lost.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
];
