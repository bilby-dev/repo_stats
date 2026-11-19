import os
import textwrap
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

# Canvas and card layout (pixels) shared by the template generator and the text
# drawn on top of it. Colors follow https://bilby-dev.github.io.
WIDTH, HEIGHT = 2300, 540
PAD = 44
RADIUS = 28
LOGO_SIZE = 200
CARDS = {
    "new_authors": (12, 12, 1028, 352),
    "authors": (12, 372, 1028, 528),
    "issues": (1272, 12, 2288, 234),
    "citations": (1272, 254, 2288, 528),
}
LOGO_CENTER = (1150, 270)

THEMES = {
    "light": {
        "bg": "#ffffff",
        "card": "#f2f7fc",
        "border": "#c4dbef",
        "ink": "#0b2540",
        "muted": "#4b6782",
        "accent": "#1d67b0",
    },
    "dark": {
        "bg": "#0a1622",
        "card": "#102233",
        "border": "#1f3850",
        "ink": "#e6eff8",
        "muted": "#9db3c9",
        "accent": "#6aa6d8",
    },
    # readable on both light and dark page backgrounds
    "transparent": {
        "bg": None,
        "card": None,
        "border": "#4f86b5",
        "ink": "#4f86b5",
        "muted": "#6f8ca8",
        "accent": "#286190",
    },
}


def make_template(theme, logo, savename):
    """
    Generate a blank dashboard template image (cards and logo, no text).

    Arguments
    ---------
    theme : str
        One of 'light', 'dark', 'transparent'
    logo : str
        Path to the logo image placed between the cards
    savename : str
        Path of the output .png
    """
    t = THEMES[theme]
    img = Image.new("RGBA", (WIDTH, HEIGHT), t["bg"] or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for box in CARDS.values():
        draw.rounded_rectangle(box, RADIUS, fill=t["card"], outline=t["border"], width=4)

    # connectors from the logo to each card
    cx, cy = LOGO_CENTER
    for x0, y0, x1, y1 in CARDS.values():
        if y0 + RADIUS < cy < y1 - RADIUS:
            draw.line([(cx, cy), (x1 if x1 < cx else x0, cy)], fill=t["border"], width=4)

    # logo on a rounded white tile, so it reads on any background
    tile = LOGO_SIZE + 24
    x0, y0 = cx - tile // 2, cy - tile // 2
    draw.rounded_rectangle(
        (x0, y0, x0 + tile, y0 + tile), 24, fill="#ffffff", outline=t["border"], width=4
    )
    logo_img = Image.open(logo).convert("RGBA").resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    img.alpha_composite(logo_img, (cx - LOGO_SIZE // 2, cy - LOGO_SIZE // 2))

    img.save(savename)
    return img


class StatsImage:
    def __init__(self, template_image, font):
        """
        Class for updating a template image (e.g. to be displayed in a GitHub README) with repository and citation statistics.

        Arguments
        ---------
        template_image : str
            Template image to be updated (see `make_template`). The theme is
            inferred from the filename ('dark', 'light', otherwise 'transparent').
        font : str
            Font file (.ttf) to be used. If a file of the same name with
            'Regular' replaced by 'SemiBold' exists, it is used for emphasis.
        """
        name = os.path.basename(template_image)
        if "dark" in name:
            self.theme = "dark"
        elif "light" in name:
            self.theme = "light"
        else:
            self.theme = "transparent"
        self.colors = THEMES[self.theme]
        self.text_color = self.colors["ink"]

        self.img = Image.open(template_image).convert("RGBA")
        self.draw = ImageDraw.Draw(self.img)

        self.font = font
        bold = font.replace("Regular", "SemiBold")
        self.font_bold = bold if os.path.exists(bold) else font
        self.font_size = 54
        self.font_instance = ImageFont.truetype(font, self.font_size)

    def _font(self, size, bold=False):
        return ImageFont.truetype(self.font_bold if bold else self.font, size)

    def draw_text(self, coords, text, text_color=None, font=None, **kwargs):
        """
        Convenience wrapper for 'PIL.ImageDraw.Draw'

        Arguments
        ---------
        coords : tuple of int
            (x,y) coordinates of text location
        text : str
            Text to be drawn
        text_color : str, default=None
            Text color
        font : 'PIL.ImageFont' instance, default=None
            Text font
        """
        if text_color is None:
            text_color = self.text_color
        if font is None:
            font = self.font_instance

        self.draw.text(coords, str(text), fill=text_color, font=font, **kwargs)

    def _label(self, card, text):
        x0, y0, _, _ = CARDS[card]
        self.draw_text(
            (x0 + PAD, y0 + 30),
            text.upper(),
            text_color=self.colors["muted"],
            font=self._font(30, bold=True),
        )

    def _big_number(self, xy, number, caption, size=96, anchor="ls"):
        """Draw a large accent-colored number followed by a caption on the same baseline."""
        font = self._font(size, bold=True)
        self.draw_text(xy, number, text_color=self.colors["accent"], font=font, anchor=anchor)
        x1 = self.draw.textbbox(xy, str(number), font=font, anchor=anchor)[2]
        self.draw_text((x1 + 18, xy[1]), caption, font=self._font(46), anchor="ls")

    def update_image(self, stats, repo_name, cache_dir):
        """
        Update the provided template image with text summarizing respository and citation statistics.

        Arguments
        ---------
        stats : dict
            A dictionary entry for each issue or pull request in the history (see `Git_metrics.get_issues_PRs`)
        repo_name : str
            Name of repository on GitHub (for drawn text)
        cache_dir : str
            Name of directory in which to cache updated image

        Returns
        -------
        self.img : 'PIL.Image' instance
            The provided template image updated with text
        """
        days = stats["age_recent_commit"]

        # new contributors, with names wrapped and shrunk to fit the card
        x0, y0, x1, y1 = CARDS["new_authors"]
        self._label("new_authors", f"New contributors · last {days} days")
        self._big_number((x0 + PAD, y0 + 150), len(stats["new_authors"]), "new contributors")

        text_authors = ", ".join(sorted(stats["new_authors"], key=str.lower))
        if not text_authors:
            text_authors = "None yet. Your first PR could be here!"
        box = (x0 + PAD, y0 + 180, x1 - PAD, y1 - 24)
        fs = 44
        while fs > 12:
            font = self._font(fs)
            # wrap to the card width at this font size
            avg_char = self.draw.textlength("abcdefghijklmnopqrstuvwxyz", font=font) / 26
            wrapped = "\n".join(textwrap.wrap(text_authors, max(10, int((box[2] - box[0]) / avg_char))))
            bbox = self.draw.multiline_textbbox(box[:2], wrapped, font=font, spacing=fs // 4)
            if bbox[2] <= box[2] and bbox[3] <= box[3]:
                break
            fs -= 1
        self.draw.multiline_text(
            box[:2], wrapped, fill=self.colors["muted"], font=font, spacing=fs // 4
        )

        # all recent contributors
        x0, y0, x1, y1 = CARDS["authors"]
        self._label("authors", f"Contributors · last {days} days")
        self._big_number(
            (x0 + PAD, y1 - 28), stats["n_recent_authors"], "people committed to the main branch", size=72
        )

        # issues and pull requests
        x0, y0, x1, y1 = CARDS["issues"]
        iss, prs = stats["issues"], stats["pullRequests"]
        self._label("issues", f"Issues & pull requests · last {iss['age_recent']} days")
        rows = [
            ("PRs", prs["recent_open"], prs["recent_close"]),
            ("Issues", iss["recent_open"], iss["recent_close"]),
        ]
        for ii, (name, n_open, n_close) in enumerate(rows):
            y = y0 + 128 + ii * 66
            self.draw_text((x0 + PAD, y), name, font=self._font(46, bold=True), anchor="ls")
            self.draw_text(
                (x0 + PAD + 190, y),
                f"{n_open} opened · {n_close} closed",
                font=self._font(46),
                anchor="ls",
            )

        # citations
        x0, y0, x1, y1 = CARDS["citations"]
        agg = stats["aggregate"]
        self._label("citations", f"Papers citing {repo_name}")
        cols = [
            (agg["cite_month"], "last month"),
            (agg["cite_year"], "this year"),
            (f"{agg['cite_all']:,}", "all time"),
        ]
        col_w = (x1 - x0 - 2 * PAD) / len(cols)
        for ii, (number, caption) in enumerate(cols):
            x = x0 + PAD + ii * col_w
            self.draw_text(
                (x, y0 + 158),
                number,
                text_color=self.colors["accent"],
                font=self._font(96, bold=True),
                anchor="ls",
            )
            self.draw_text((x, y0 + 204), caption, font=self._font(40), anchor="ls")

        now = datetime.now(timezone.utc).strftime("%B %d, %Y")
        self.draw_text(
            (x1 - PAD, y1 - 22),
            f"Generated {now}",
            text_color=self.colors["muted"],
            font=self._font(28),
            anchor="rs",
        )

        self.img.save(f"{cache_dir}/{repo_name}_user_stats_{self.theme}.png")

        return self.img


if __name__ == "__main__":
    # regenerate the template images in dashboard_template/
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard_template")
    for theme in THEMES:
        make_template(
            theme,
            os.path.join(here, "bilby_logo.jpg"),
            os.path.join(here, f"user_stats_template_{theme}.png"),
        )
