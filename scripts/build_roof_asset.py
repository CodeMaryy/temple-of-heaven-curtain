from math import sqrt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "temple-roof-enhanced-v2.png"
OUTPUT = ROOT / "assets" / "temple-roof-cutout.png"
WEB_OUTPUT = ROOT / "assets" / "temple-roof-cutout-web.png"
PREVIEW = ROOT / "work" / "roof-cutout-preview.png"


def smoothstep(low: float, high: float, value: float) -> float:
    amount = max(0.0, min(1.0, (value - low) / (high - low)))
    return amount * amount * (3.0 - 2.0 * amount)


image = Image.open(SOURCE).convert("RGBA")
width, height = image.size
pixels = image.load()

# The paper tone is sampled from all four corners so the matte follows the
# generated asset instead of relying on a hard-coded beige value.
corner = max(24, min(width, height) // 18)
samples = []
for offset_x in (0, width - corner):
    for offset_y in (0, height - corner):
        for y in range(offset_y, offset_y + corner, 3):
            for x in range(offset_x, offset_x + corner, 3):
                samples.append(pixels[x, y][:3])

paper = tuple(sum(sample[channel] for sample in samples) / len(samples) for channel in range(3))
alpha_values = []
center_x = width / 2
roof_half_width = width * 0.32


def is_red_wall(red: int, green: int, blue: int) -> bool:
    return red > 82 and red - green > 34 and green - blue < 48


# Locate the blue/gold eave-to-red-wall transition independently for every
# column. A short consecutive run avoids treating isolated warm ornament as the
# facade. Columns beyond the facade retain the full projected eave edge.
roof_edges = []
fallback_edges = []
search_start = round(height * 0.68)
search_end = round(height * 0.89)
for x in range(width):
    normalized_x = min(1.0, abs(x - center_x) / roof_half_width)
    fallback = height * 0.77 + height * 0.07 * (normalized_x ** 1.65)
    fallback_edges.append(fallback)
    consecutive = 0
    transition = None
    for y in range(search_start, search_end):
        red, green, blue, _ = pixels[x, y]
        consecutive = consecutive + 1 if is_red_wall(red, green, blue) else 0
        if consecutive >= 5:
            transition = y - consecutive + 1
            break
    roof_edges.append(min(fallback, transition - 3) if transition is not None else fallback)

# Median smoothing keeps ornamental details from producing a jagged matte.
smoothed_edges = []
window = 15
for x in range(width):
    values = sorted(roof_edges[max(0, x - window): min(width, x + window + 1)])
    smoothed_edges.append(values[len(values) // 2])

for y in range(height):
    for x in range(width):
        red, green, blue, _ = pixels[x, y]
        distance = sqrt(
            (red - paper[0]) ** 2
            + (green - paper[1]) ** 2
            + (blue - paper[2]) ** 2
        )
        chroma = max(red, green, blue) - min(red, green, blue)
        luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722

        # Paper texture and the old soft shadow are comparatively neutral.
        # Blue, green, gold, and dark architectural linework remain opaque.
        matte = smoothstep(28, 78, distance)
        if chroma < 24 and luminance > 86:
            matte *= smoothstep(38, 88, distance)
        if red >= green >= blue and chroma < 75 and luminance > 110:
            matte *= smoothstep(62, 118, distance)

        roof_edge = min(smoothed_edges[x], fallback_edges[x])
        edge_feather = height * 0.009
        if y > roof_edge - edge_feather:
            matte *= 1.0 - smoothstep(roof_edge - edge_feather, roof_edge, y)

        alpha_values.append(round(255 * matte))

# The source has an asymmetric painted shadow to the right. Clamp only
# low-saturation right-side pixels to the mirrored left-side silhouette so the
# roof remains intact while the old shadow is removed from the cutout asset.
for y in range(height):
    for x in range(width // 2, width):
        red, green, blue, _ = pixels[x, y]
        chroma = max(red, green, blue) - min(red, green, blue)
        luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
        if x > width * 0.67 and y > height * 0.38 and chroma < 90 and luminance > 68:
            index = y * width + x
            mirror_index = y * width + (width - 1 - x)
            alpha_values[index] = min(alpha_values[index], alpha_values[mirror_index])

# Fill light ornament inside the detected architectural silhouette. Without
# this pass, pale blue and gold panels can be mistaken for the paper because
# their RGB values are locally similar even though they sit between dark eaves.
scan_left = round(width * 0.12)
scan_right = round(width * 0.88)
for y in range(height):
    row_offset = y * width
    confident = [
        x for x in range(scan_left, scan_right)
        if alpha_values[row_offset + x] > 220
    ]
    if len(confident) < 20:
        continue
    left_edge = min(confident)
    right_edge = max(confident)
    left_span = center_x - left_edge
    right_span = right_edge - center_x
    symmetric_span = min(width * 0.39, max(left_span, right_span))
    fill_left = max(0, round(center_x - symmetric_span))
    fill_right = min(width, round(center_x + symmetric_span))
    for x in range(fill_left, fill_right):
        restored_edge = min(smoothed_edges[x], fallback_edges[x])
        if y < restored_edge - height * 0.003:
            alpha_values[row_offset + x] = max(alpha_values[row_offset + x], 245)

alpha = Image.new("L", image.size)
alpha.putdata(alpha_values)
alpha = alpha.filter(ImageFilter.GaussianBlur(0.7))

# Remove only the final dark-red facade flecks that can survive inside the
# feathered edge. The stricter channel test avoids blue tile and gold ornament.
clean_alpha = list(alpha.get_flattened_data())
for y in range(round(height * 0.68), height):
    for x in range(round(width * 0.42), width):
        red, green, blue, _ = pixels[x, y]
        near_edge = y > smoothed_edges[x] - height * 0.022
        red_fleck = (
            red > 48
            and red - green > 36
            and red - blue > 54
            and green - blue < 34
        )
        if near_edge and red_fleck:
            clean_alpha[y * width + x] = 0
alpha.putdata(clean_alpha)
alpha = alpha.filter(ImageFilter.GaussianBlur(0.35))

image.putalpha(alpha)
image.save(OUTPUT, optimize=True)

bounds = alpha.getbbox()
if bounds is None:
    raise RuntimeError("Roof matte is empty")
padding = 8
left = max(0, bounds[0] - padding)
top = max(0, bounds[1] - padding)
right = min(width, bounds[2] + padding)
bottom = min(height, bounds[3] + padding)
web_image = image.crop((left, top, right, bottom))
web_image.save(WEB_OUTPUT, optimize=True)

PREVIEW.parent.mkdir(parents=True, exist_ok=True)
checker = Image.new("RGBA", image.size, (224, 224, 224, 255))
draw = ImageDraw.Draw(checker)
tile = 40
for y in range(0, height, tile):
    for x in range(0, width, tile):
        if (x // tile + y // tile) % 2:
            draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(190, 190, 190, 255))
checker.alpha_composite(image)
checker.save(PREVIEW, optimize=True)

print(f"Wrote {OUTPUT} ({width}x{height}), paper RGB {tuple(round(value) for value in paper)}")
print(f"Wrote {WEB_OUTPUT} ({web_image.width}x{web_image.height}), source crop {(left, top, right, bottom)}")
