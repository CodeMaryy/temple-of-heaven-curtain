# Temple of Heaven Curtain

An interactive editorial portrait of Beijing's Temple of Heaven. The hanging
Chinese character curtain uses a lightweight Verlet-style simulation and
responds to pointer movement.

## Live Site

[Open the Temple of Heaven Curtain](https://codemaryy.github.io/temple-of-heaven-curtain/)

## Local Preview

The published experience is a static site. Start any local HTTP server from the
repository root, for example:

```bash
python3 -m http.server 4173
```

Then open `http://127.0.0.1:4173/`.

## Controls

Use the Configure panel to tune interaction strength, reach, and inertia, or to
reset the curtain.

## Deployment

GitHub Pages serves `index.html` and the `assets/` directory directly from the
root of the `main` branch at
`https://codemaryy.github.io/temple-of-heaven-curtain/`.
