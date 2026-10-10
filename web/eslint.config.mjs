import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Cac effect fetch-on-mount/deps-change o day deu da co "cancelled"
      // flag dung chuan de tranh set-state-after-unmount; rule nay (huong
      // toi React Compiler) coi viec goi setState(true)/setState(null) ngay
      // dau effect la "khong toi uu" nhung khong phai loi, va la pattern
      // loading-state rat pho bien - ha xuong warn thay vi chan build.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
