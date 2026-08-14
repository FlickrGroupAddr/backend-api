import { mount } from "svelte";
import App from "./App.svelte";
import "./app.css";

/**
 * Svelte 5 mounts with `mount()`. **`new App({ target })` is the Svelte 4 form** and
 * still appears in most tutorials; it throws here.
 */
const target = document.getElementById("app");
if (target === null) {
	throw new Error("No #app element. index.html and main.ts disagree.");
}

export default mount(App, { target });
