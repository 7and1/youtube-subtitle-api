import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts", "src/webhook.ts"],
  format: ["esm", "cjs"],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  target: "es2022",
  minify: false,
  esbuildOptions(options) {
    options.conditions = ["module"];
  },
  define: {
    __VERSION__: JSON.stringify(process.env.npm_package_version || "1.0.0"),
  },
});
