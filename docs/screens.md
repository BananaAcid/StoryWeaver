# Screenshots Slideshow

Animated slideshow generated from `docs/screens/` PNG files using ffmpeg.

## Image order

Screenshots are ordered: `.en` files first (alphabetical), then `.de` files (alphabetical).

```
app-intro.en.png
app-stories.en.png
app-story-details.en.png
app-story-page-1.en.png
app-story-page-1-options.en.png
app-intro.de.png
app-stories.de.png
app-stories-fav.de.png
app-story-details.de.png
app-story-page-1.de.png
app-story-page-1-options.de.png
```

## Concat file

- `concat.txt` — 3s per frame (in `docs/`, image paths prefixed with `screens/`)

## ffmpeg commands

Run from `docs/`. The slideshow is generated at the original screenshot resolution (640x480, 3s per frame).

### WebP (primary)

```bash
ffmpeg -f concat -safe 0 -i concat.txt -vf "scale=640:-1" -loop 0 screens/screens.webp -y
```

### GIF (fallback)

```bash
ffmpeg -f concat -safe 0 -i concat.txt -vf "scale=640:-1" -loop 0 screens/screens.gif -y
```

## Output files

| File | Format | Delay | Duration | Resolution |
|------|--------|-------|----------|------------|
| `screens.webp` | WebP | 3s | 33s | 640x480 |
| `screens.gif` | GIF | 3s | 33s | 640x480 |
