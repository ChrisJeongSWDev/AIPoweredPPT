# Layout Catalog

Generated from `Vieworks_R&D_ppt_Template.pptx` (sha256 `0de7d70cf451...`) by `analyze_pptx_master.py`.
**Do not hand-edit** -- re-run the analyzer instead.

- Slide size: **13.3333in x 7.5in** (16:9), 12192000 x 6858000 EMU
- Masters: **1** | Layouts (first master): **5** | Existing slides: **23**

## Master 0: 

- Theme: `Office 테마`
- Major font (headings): latin `맑은 고딕` / east-asian ``
- Minor font (body): latin `맑은 고딕` / east-asian ``
- Brand accent `#DB0032`: not-found
- Colour map: dk1=#000000, lt1=#FFFFFF, dk2=#44546A, lt2=#E7E6E6, accent1=#4472C4, accent2=#ED7D31, accent3=#A5A5A5, accent4=#FFC000, accent5=#5B9BD5, accent6=#70AD47, hlink=#0563C1, folHlink=#954F72

### Layouts

| # | layout_id | role | placeholders |
|---|-----------|------|--------------|
| 0 | `제목 슬라이드` | title | BODY(idx 10), BODY(idx 11) |
| 1 | `사용자 지정 레이아웃` | blank | -none- |
| 2 | `1_사용자 지정 레이아웃` | custom | BODY(idx 10), BODY(idx 11), BODY(idx 12) |
| 3 | `2_사용자 지정 레이아웃` | custom | BODY(idx 10) |
| 4 | `3_사용자 지정 레이아웃` | blank | -none- |

### Content budgets

The AI author MUST respect these. `cjk` applies to Korean text, `latin` to English;
for mixed text, budget against `cjk`.

**`제목 슬라이드`** (title)

- `idx 10` BODY -- 10.6233x0.5608in @ 36.0pt -- max **1 bullets** x **6 words** (36 latin / 19 korean chars per bullet)
- `idx 11` BODY -- 10.6233x0.5608in @ 16.0pt -- max **1 bullets** x **13 words** (82 latin / 43 korean chars per bullet)

**`1_사용자 지정 레이아웃`** (custom)

- `idx 10` BODY -- 5.9876x0.4848in @ 28.0pt -- max **1 bullets** x **4 words** (26 latin / 13 korean chars per bullet)
- `idx 11` BODY -- 5.9876x0.4848in @ 36.0pt -- max **1 bullets** x **3 words** (20 latin / 10 korean chars per bullet)
- `idx 12` BODY -- 5.9876x0.4848in @ 16.0pt -- max **1 bullets** x **7 words** (46 latin / 24 korean chars per bullet)

**`2_사용자 지정 레이아웃`** (custom)

- `idx 10` BODY -- 10.0734x0.5174in @ 30.0pt -- max **1 bullets** x **6 words** (41 latin / 21 korean chars per bullet)

---

## Allowed `layout_id` values

The IR `layout_id` field MUST be exactly one of:

- `제목 슬라이드`  (title)
- `사용자 지정 레이아웃`  (blank)
- `1_사용자 지정 레이아웃`  (custom)
- `2_사용자 지정 레이아웃`  (custom)
- `3_사용자 지정 레이아웃`  (blank)

