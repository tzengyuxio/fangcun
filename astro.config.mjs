// @ts-check
import { defineConfig, passthroughImageService } from 'astro/config';

// https://astro.build/config
// NOTE: `base` assumes GitHub Pages at tzengyuxio.github.io/fangcun.
// Adjust `site`/`base` if a custom domain is configured (see docs/build-plan.md Phase 0).
export default defineConfig({
  site: 'https://tzengyuxio.github.io',
  base: '/fangcun',
  output: 'static',
  // Static reference site: serve images as-is, no on-the-fly transforms.
  // Avoids the native `sharp` dependency (also keeps CI `npm ci` lean).
  image: { service: passthroughImageService() },
});
