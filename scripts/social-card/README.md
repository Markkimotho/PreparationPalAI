# Link-preview image

`frontend/public/social-preview.png` (1200 x 630) is what shows when someone shares the site. It is drawn
by `card.html` from the landing page's own stylesheet, so it matches the site.

After changing the landing design, re-render:

```bash
scripts/social-card/render.sh        # headless Brave or Chrome; checks the size
```

If headless rendering is unavailable (it can hang without a display), open `card.html` in a browser at a
viewport of at least 1200 x 630, take a screenshot, and crop the top-left 1200 x 630.
`tests/test_public_site.py` fails if the image is not 1200 x 630.
