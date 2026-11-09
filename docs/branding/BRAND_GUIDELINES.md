# JobPilot — Brand & Logo Guidelines

> Official visual identity and asset specification for JobPilot.

---

## 1. The Core Identity & Metaphor

* **The Metaphor:** A focused, friendly robotic mascot operates a sleek floating laptop terminal, while a **certified job application document** (with checkmark badge and aerodynamic contrails) ascends upward into the sky.
* **The Story:** JobPilot eliminates chaotic, repetitive manual job application stress with **autonomous velocity, pilot precision, and verified career trajectory**. The bot works continuously to prepare, tailor, and submit high-match applications.
* **Key Design Pillars:**
  1. **Vertical Stacked Lockup:** Modern square-profile hierarchy placing the robot mascot centered on top, followed directly by the balanced "JobPilot" wordmark and "CAREER AUTOPILOT" pill.
  2. **Unmistakable Intention:** A real folded document with lines of resume content and a certified checkmark badge, eliminating any ambiguity or "music/play button" misinterpretations.
  3. **Multi-Tonal Character:** High-contrast Slate and Obsidian body, glowing cyan pilot eyes, and vibrant safety-orange accents on the antenna and aviator earcups.
  4. **Floating Agility:** Replaces heavy wooden desks with an ultra-thin modern floating laptop with glowing screen horizon and resting bot hands.

---

## 2. Official Color Palette

| Role | Name | HEX | RGB | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Accent** | **Safety Orange** | `#FF5F15` | `255, 95, 21` | Certified check badge, flight arrows, "Pilot" wordmark, antenna beacon |
| **Primary Neutral** | **Obsidian Slate** | `#0F172A` | `15, 23, 42` | Robot chassis, "Job" wordmark (light mode), primary document stroke |
| **Secondary Accent**| **Sky Cyan** | `#0EA5E9` / `#38BDF8` | `14, 165, 233` | Luminous visor eyes, laptop screen glow |
| **Hardware Neutral**| **Aluminum Slate** | `#334155` / `#1E293B` | `51, 65, 85` | Laptop keyboard base, visor slot, earcups |
| **Dark Canvas** | **App Obsidian** | `#0F1117` | `15, 17, 23` | Dark mode surface, application background, desktop icon tiles |
| **Light Canvas** | **Pure White** | `#FFFFFF` | `255, 255, 255` | Document sheet, light backgrounds, checkmark glyph |

---

## 3. Logo Formats & Master Assets

| Asset | Format | Purpose | File Path |
| :--- | :--- | :--- | :--- |
| **Vertical Stacked (Light)** | SVG / PNG | Primary official logo for light surfaces & documentation | [`jobpilot-stacked-color.svg`](./jobpilot-stacked-color.svg) |
| **Vertical Stacked (Dark)** | SVG / PNG | Primary official logo for dark UI, GitHub, & splash screens | [`jobpilot-stacked-dark.svg`](./jobpilot-stacked-dark.svg) |
| **Standalone Symbol (Color)**| SVG / PNG | Avatar, profile pictures, social marks, roundels | [`jobpilot-symbol-color.svg`](./jobpilot-symbol-color.svg) |
| **Standalone Symbol (Dark)** | SVG / PNG | Dark UI symbol mark and splash screen icon | [`jobpilot-symbol-dark.svg`](./jobpilot-symbol-dark.svg) |
| **App Icon Tile** | SVG / PNG | Desktop application launcher, Linux desktop entry | [`exports/jobpilot-brand-app-icon.svg`](./exports/jobpilot-brand-app-icon.svg) |
| **Square Avatar Tile** | SVG / PNG | Social avatars, GitHub profile, marketplace cards | [`exports/jobpilot-brand-square.svg`](./exports/jobpilot-brand-square.svg) |
| **Favicon & Web Icons** | ICO / PNG | Web dashboard, browser tabs, PWA manifest | [`exports/favicon.ico`](./exports/favicon.ico) |
| **One-Color Black** | SVG / PNG | Single-color black documentation & laser printing | [`exports/jobpilot-brand-black.svg`](./exports/jobpilot-brand-black.svg) |
| **One-Color White** | SVG / PNG | Single-color white reversed for solid dark materials | [`exports/jobpilot-brand-white.svg`](./exports/jobpilot-brand-white.svg) |

---

## 4. Typography & Wordmark Clearance Specifications

* **Grid & Canvas:** `viewBox="0 0 480 480"` (Aspect Ratio 1:1 Square).
* **Optical Center:** Horizontal center point is fixed at `X = 240`.
* **Wordmark Scaling:** The compound outlined vector wordmark "JobPilot" is uniformly scaled to `0.78` and positioned at `translate(87, 280)`.
* **Letter Visibility & Margins:**
  * **Left Margin (start of 'J'):** `88.6 px`
  * **Right Margin (end of 't'):** `85.7 px`
  * **Status:** Complete equidistance with ~86px of clear protective margin on both sides. The letter 't' in "Pilot" is 100% visible with zero boundary clipping.
* **Tagline Pill:** "CAREER AUTOPILOT" is rendered via pure stroked vector paths inside an SVG pill capsule (zero external font dependencies).

---

## 5. Usage Rules (Do's & Don'ts)

* **DO** use the vertical stacked lockup as the default master for all official presentations, marketing decks, and primary documentation.
* **DO** maintain the minimum clear space of at least 15% canvas margin around the logo.
* **DO** use [`jobpilot-stacked-dark.svg`](./jobpilot-stacked-dark.svg) on dark backgrounds (`#0F1117` or darker).
* **DON'T** compress, stretch, skew, or distort the vector mark.
* **DON'T** reintroduce unscaled text that touches or exceeds the canvas borders.
* **DON'T** apply drop shadows, raster blurs, or 3D embossing to the clean vector shapes.
