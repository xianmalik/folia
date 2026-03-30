# Customization Guide

All visual styling lives in `core/`. Edit the relevant file and run `make build` to see the result.

---

## Accent color

Edit `core/colors.tex`:

```latex
\definecolor{accentcolor}{HTML}{DC3522}  % change this hex
```

To disable the colored section titles entirely:

```latex
\setbool{acvSectionColorHighlight}{false}
```

Or set it per-document in `resume.tex`:

```latex
\setbool{acvSectionColorHighlight}{false}
```

---

## Text colors

Also in `core/colors.tex`. The palette maps logical names to hex colors:

| Name            | Used for                        |
|-----------------|---------------------------------|
| `darktext`      | Entry titles                    |
| `text`          | Body text, section titles       |
| `graytext`      | Positions, dates, locations     |
| `lighttext`     | Address, social icons           |
| `sectiondivider`| Horizontal rule after sections  |

---

## Fonts and weights

Edit `core/fonts.tex`. Inter is loaded as a variable font — weights are set via `RawFeature`:

```latex
\newcommand*{\headerfont}{\fontspec{Inter}[RawFeature = {+wght=700}]}
\newcommand*{\bodyfont}{\fontspec{Inter}[RawFeature = {+wght=400}]}
\newcommand*{\bodyfontlight}{\fontspec{Inter}[RawFeature = {+wght=300}]}
```

Common weight values: `100` thin · `300` light · `400` regular · `500` medium · `700` bold · `900` black.

To use a different font, place the `.ttf` or `.otf` file in `font/` and update the `\setmainfont` block and `\fontspec` calls.

---

## Page margins

Edit `core/layout.tex`:

```latex
\geometry{left=2.0cm, top=1.5cm, right=2.0cm, bottom=2.0cm, footskip=.5cm}
```

Or override per-document in `resume.tex` (already done for tighter margins):

```latex
\geometry{left=1.4cm, top=.8cm, right=1.4cm, bottom=1.8cm, footskip=.5cm}
```

---

## Font sizes for sections and entries

Edit `core/styles.tex`. Each element has its own style command:

```latex
\newcommand*{\entrytitlestyle}[1]{{\fontsize{12pt}{1em}\headerfont\color{darktext} #1}}
\newcommand*{\entrydatestyle}[1]{{\fontsize{8pt}{1em}\bodyfont\slshape\color{graytext} #1}}
\newcommand*{\sectionstyle}[1]{{\fontsize{12pt}{1em}\bfseries\color{text} #1}}
```

---

## Section spacing

Edit `core/commands.tex`:

```latex
\newcommand{\acvSectionTopSkip}{3mm}        % space above each section title
\newcommand{\acvSectionContentTopSkip}{2.5mm} % space between title and first entry
```

---

## Reordering or hiding sections

Edit `resume.tex`. Comment out a section to hide it; reorder the `\input` lines to change display order:

```latex
\input{sections/00-summary.tex}
\input{sections/10-experience.tex}
\input{sections/20-projects.tex}
\input{sections/30-skills.tex}
\input{sections/40-education.tex}
% \input{sections/50-languages.tex}   ← commented out = hidden
```

---

## Bold text in YAML

Use `[[double brackets]]` around any text in your YAML data files to render it bold in the PDF:

```yaml
items:
  - Reduced build time by [[40%]] by migrating to a monorepo
```
