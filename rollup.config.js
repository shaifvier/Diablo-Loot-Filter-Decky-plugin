import deckyPlugin from "@decky/rollup";
const preview = process.env.DECKY_PREVIEW === "1";
const config = deckyPlugin({}, preview ? "./preview" : ".");
// @decky/rollup merges defaults after overrides; set the output after creation.
config.output.dir = preview ? "dist-preview" : "dist";
export default config;
