---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope:
  - GEM_Knowledge_API.md
  - GEM_Knowledge.md
  - Gemini_Web_Prompt.md
claude_model: sonnet
read_refs: N/A
change_detail_path: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/scratch/change_detail_phase1.md
---

# Phase 1: Unified Design Style Template

Apply the WorkDirector's exact changes to unify the design templates.

## Instructions
Please strictly follow the WorkDirector's output to edit the target files:

I have enough grounding. Here is the WorkDirector output.

---

# Phase 1 ??Enhanced Work Order: Unified Design Style Guide (`GEM_Knowledge_API.md` 짠8)

**Role of this document:** strengthened brief + verified context for the *next* edit phase. No files were modified by this session (read-only director).

---

## A. Verified context (read from the target repo, with citations)

**A1. `GEM_Knowledge_API.md` is loaded verbatim as the API system prompt.**
`src/aippt/canvas/app.py:156` ??`PROMPT_PATH = Path(__file__).resolve().parents[3] / "GEM_Knowledge_API.md"`, read whole by `system_instruction()` (`app.py:766-772`) and passed as `system=` to `CliWorkerClient.complete_json()` (`app.py:868`). Anything added to this file becomes system-prompt text on every live generation.

**A2. "Gemini and Sonnet 5" are two *different* delivery paths, and only one reads this file.**
- `MODEL_PROFILES` in this repo is `{"sonnet": "Claude Sonnet 5", "opus": "Claude Opus"}`, `DEFAULT_PROFILE = "sonnet"`, both `backend: "claude"` (`app.py:110-118`). This is the path that reads `GEM_Knowledge_API.md`.
- Gemini is the **manual web-paste path**: `GEM_Knowledge.md` and `Gemini_Web_Prompt.md` are pasted into gemini.google.com. No code reads them (grep: zero references outside docs). `app.py:153-155` *claims* the contract is "kept in one file so the two paths cannot drift" ??**that claim is currently false**; there are three prompt files and they have already drifted (see A5).
- **Consequence:** editing `GEM_Knowledge_API.md` alone unifies style for Sonnet/Opus only. Gemini keeps its old style until 짠8 is propagated. This is called out as a mandatory follow-up in 짠F, and 짠8 must be authored as a **self-contained, copy-pasteable block** so propagation is a pure copy, not a rewrite.

**A3. Hard constraints the style guide must not contradict (enforced in code):**

| Constraint | Source | Note |
|---|---|---|
| `#4472C4` is **rejected** (theme accent1) | `validate.py:59,291-300`; `schema.json:261` | Hard validation failure, not a style preference |
| `fill` is **required** even when `null` | `schema.json:82,265` | Omitted fill ??silent accent1 inheritance |
| run `color` is **required** on every run | `schema.json:349,363-366` | Uncoloured run inherits `lt1` = **white** |
| HEADER reject box `(0, 0, 960, 92)` | `geometry.py:49` | Edge contact is legal: `y == 92` does **not** intersect (`geometry.py:69-77`) |
| FOOTER reject box `(733.6, 500, 960, 540)` | `geometry.py:50` | Real box is **narrower** than the doc's full-width rule; keep the doc's stricter rule (a safe superset) |
| BODY_SAFE `(45.6, 92, 914.4, 500)` | `geometry.py:51` | Advisory in code, mandatory in the prompt |
| Title auto-renders at **30 pt, `#000000`, LEFT**, placeholder idx 10 | `render_canvas.py:46-55,58-85` | Not an element; never in `elements` |
| Fonts are **fixed**, not model-selectable | `style.py:47-48` ??`Century Gothic` + `留묒? 怨좊뵓` | There is no font field in the schema |
| Line-height fixed 1.2, para spacing 0 | `style.py:191-193` | |
| Text-frame margins 7.2 L/R, 3.6 T/B; **no autofit** | `style.py:177-180` | Overflow spills silently ??size discipline matters |
| `target` must be **omitted** by the model | `app.py:775-808` | Server injects it from the live pin; 짠7 examples correctly omit it |

**A4. Model output is schema-validated before it reaches the user** (`app.py:854-858`, `ai_adapter.py`), with two silent repairs: missing `arrow` ??`"none"`, missing run `color` ??`#1A1A1A` (`app.py:813-827`). 짠8 should adopt `#1A1A1A` as body ink so the fallback and the guide agree.

**A5. The brand-red conflict is real, pre-existing, and documented.**
- Code-authoritative: `#FF0032` ??`style.py:50` `BRAND_RED`, `validate.py:60`, `schema.json:261` ("`#FF0032` (brand red) is the default for new content"), mock deck card fill (`app.py:928`), and an explicit **user override on record**: `renderer_brief.md:77-78` ("You MUST default to `#FF0032` ??Do NOT use `#DB0032`").
- Prompt docs say `#E63312` ??`GEM_Knowledge_API.md:48`, `GEM_Knowledge.md:46`, `Gemini_Web_Prompt.md:13,27`.
- Already flagged and deliberately deferred once: `phase4_brief.md:539`, `phase4_change_detail.md:108` ("unifying the two reds is out of scope for this brief"). **Phase 1 is where it gets resolved.**

**A6. The 짠7 few-shot examples are the *de facto* style guide.** They currently use `#0052CC` (Atlassian blue) and `#F4F5F7` ??colours that appear **nowhere else in the codebase**. In practice an LLM copies the examples over the prose rules. **A 짠8 that contradicts 짠7 will not change model behaviour.** Rewriting 짠7 to 짠8's tokens is therefore not optional polish; it is the load-bearing half of this task.

**A7. Existing house style, from the mock deck** (`app.py:903-1025`) ??the only rendered-and-reviewed reference layout: `_PAPER #FFFFFF`, `_INK #1A1A1A`, `_MUTED #6B727C`; content band x 60 ??900 (w 840); 3 cards w 244 at x 60/358/656 (gutter 54); sizes 20 bold / 18 bold / 14 / 13 / 12.

**A8. No test touches this file.** `grep -rn "system_instruction|PROMPT_PATH|GEM_Knowledge" tests/` ??zero hits. The edit is test-neutral; do not expect a gate to confirm it.

---

## B. Decisions required ??with the director's recommendation

The next worker must **not** leave two options in the file. Each decision below is pre-resolved; deviate only with a written rationale in the change-detail.

**D-1 ??PRIMARY colour: `#FF0032` (brand red).** *Recommended, and treat as decided.*
Rationale: it is the only value with code authority (A5) and it is backed by a recorded user override. The brief's `#0052CC` example is descriptive of the file's current state, not a mandate; `#0052CC` has no provenance in this project. **If the owner overrides this to `#0052CC`, the substitution must be applied in 짠5, 짠7 and 짠8 together ??a mixed state is worse than either choice.**

**D-2 ??Connector colour is `#1A1A1A`, never brand red.**
짠3 forbids mimicking the template's red gradient divider. Red *fills* on body shapes are sanctioned (the mock deck does exactly that), but a thin red **line** is confusable with template chrome. Both existing 짠7 examples already use `#1A1A1A`. 짠8 must state this distinction explicitly ??it is precisely the kind of unstated tension that produces divergent output across models.

**D-3 ??Alpha (`#RRGGBBAA`) is forbidden in AI-generated output.**
짠5 documents alpha as *legal* (schema.json:260). 짠8 narrows it to *not chosen*. Framing to use throughout: **짠5 says what the schema permits; 짠8 says what you must actually pick.** 짠8 narrows 짠1?벬? and never contradicts them. Alpha remains available to the human editor.

**D-4 ??"Title = 24" from the brief means the *section heading inside a textbox*, not the slide title.**
The slide title is auto-rendered at 30 pt and 짠3 already forbids a title element. 짠8 must say this in one sentence or a worker/model will reintroduce the duplicate-title bug 짠3 exists to prevent.

---

## C. The exact content to add ??`## 8. ?듭씪 ?붿옄???ㅽ???媛?대뱶 (STRICT TEMPLATE)`

Insert **after 짠7** (last section of the file). Korean, to match the document. All arithmetic below was hand-verified against `x ??[45.6, 914.4]`, `y ??[92, 500]`.

````markdown
---

## 8. ?듭씪 ?붿옄???ㅽ???媛?대뱶 (STRICT TEMPLATE)

**???뱀뀡? 짠1~짠7??"?덉슜 踰붿쐞"瑜?醫곹엳??媛뺤젣 洹쒖튃?낅땲??** 짠5媛 "?ㅽ궎留덇? ?덉슜?섎뒗 寃???
留먰븳?ㅻ㈃, 짠8? "?뱀떊??諛섎뱶???좏깮?댁빞 ?섎뒗 寃???留먰빀?덈떎. 짠7 ?덉떆? 짠8??異⑸룎?섎㈃ 짠8??
?곗꽑?⑸땲?? ?꾨옒 ?쒖뿉 ?녿뒗 ?됱긽 肄붾뱶, ?고듃 ?ш린, 醫뚰몴??**?ъ슜 湲덉?**?낅땲??

### 8.1. ?됱긽 ?좏겙 (??6媛쒕쭔 ?ъ슜)

| ?좏겙 | 肄붾뱶 | ?⑸룄 |
|---|---|---|
| PRIMARY | `#FF0032` | 媛뺤“ ?꾪삎 梨꾩슦湲? ?듭떖 移대뱶 |
| SECONDARY | `#6B727C` | 蹂댁“ ?꾪삎 梨꾩슦湲? 遺媛 ?ㅻ챸 ?띿뒪?? ?뉗? ?뚮몢由?|
| SURFACE | `#F4F5F7` | 以묐┰ 諛곌꼍 移대뱶/?⑤꼸 梨꾩슦湲?|
| INK | `#1A1A1A` | 諛앹? 諛곌꼍 ?꾩쓽 蹂몃Ц ?띿뒪?? 紐⑤뱺 ?곌껐??|
| PAPER | `#FFFFFF` | PRIMARY/SECONDARY 梨꾩슦湲??꾩쓽 ?띿뒪??|
| (?놁쓬) | `null` | ?щ챸 諛곌꼍 (textbox 湲곕낯媛? |

- **湲덉? ?됱긽 `#4472C4`**: ?쒗뵆由??뚮쭏 ?됱긽?낅땲?? ?ъ슜 ???뚮뜑留곸씠 **?섎뱶 ?ㅽ뙣**?⑸땲??
- **?щ챸??Alpha) 湲덉?**: `#RRGGBBAA` 8?먮━ ?뺤떇??異쒕젰?섏? 留덉꽭?? ??긽 6?먮━ `#RRGGBB`留?
  ?ъ슜?⑸땲??
- **?鍮?洹쒖튃**: PRIMARY/SECONDARY 梨꾩슦湲????띿뒪?몃뒗 諛섎뱶??PAPER. SURFACE ?먮뒗 `null`
  梨꾩슦湲????띿뒪?몃뒗 諛섎뱶??INK (蹂댁“ ?ㅻ챸留?SECONDARY ?덉슜).
- **鍮④컙 ??湲덉?**: ?곌껐??`connector`)??`color`??**??긽 INK `#1A1A1A`** ?낅땲?? 鍮④컙???좎?
  ?쒗뵆由우씠 ?먮룞 ?쎌엯?섎뒗 ?곷떒 洹몃씪?곗씠??援щ텇?좉낵 ?쇰룞?섎?濡??덈? 洹몃━吏 留덉꽭??(짠3 李몄“).
  鍮④컙?됱? "?????꾨땲??"硫?梨꾩슦湲?"?쇰줈留??ъ슜?⑸땲??

### 8.2. 醫뚰몴 洹몃━??(??媛믩쭔 ?ъ슜)

蹂몃Ц ?곸뿭? **x: 60.0 ~ 900.0 (?덈퉬 840.0)** ?쇰줈 怨좎젙?⑸땲?? ?꾩쓽??x 醫뚰몴瑜?留뚮뱾吏 留덉꽭??

**??Column) ??移대뱶媛 ?쒕줈 ?⑥뼱???덉쓣 ??(媛꾧꺽 30.0):**

| ??媛쒖닔 | `w` | `x` 媛?|
|---|---|---|
| 2 | 405.0 | 60.0 / 495.0 |
| 3 | 260.0 | 60.0 / 350.0 / 640.0 |
| 4 | 187.5 | 60.0 / 277.5 / 495.0 / 712.5 |
| 5 | 144.0 | 60.0 / 234.0 / 408.0 / 582.0 / 756.0 |

**??Column) ??移대뱶瑜??붿궡?쒕줈 ?곌껐????(媛꾧꺽 54.0):**

| ??媛쒖닔 | `w` | `x` 媛?|
|---|---|---|
| 2 | 393.0 | 60.0 / 507.0 |
| 3 | 244.0 | 60.0 / 358.0 / 656.0 |
| 4 | 169.5 | 60.0 / 283.5 / 507.0 / 730.5 |

**??Row) ??`y`? `h`???꾨옒 議고빀留??ъ슜:**

| ?대쫫 | `y` | `h` | ?⑸룄 |
|---|---|---|---|
| LEAD | 112.0 | 56.0 | ?쒕ぉ ?꾨옒 ??以??붿빟 (textbox, `fill: null`) |
| ROW-A | 200.0 | 120.0 | 蹂몃Ц 移대뱶 1??(湲곕낯媛? |
| ROW-A-TALL | 200.0 | 160.0 | 移대뱶媛 1?됰퓧?닿퀬 ?댁슜??留롮쓣 ??|
| ROW-B | 350.0 | 120.0 | 蹂몃Ц 移대뱶 2??(ROW-A? ?④퍡 ???뚮쭔) |
| NOTE | 452.0 | 36.0 | ?섎떒 媛곸＜ (ROW-B瑜??곗? ?딆쓣 ?뚮쭔) |

- **?뺤궗媛??꾪삎(`ellipse`, `triangle`)**: `w = h = 120.0`, ?뚯냽 ?댁쓽 媛?대뜲??諛곗튂.
  (?? 3???곌껐 洹몃━??1??`x=60.0, w=244.0` ???먯쓽 `x = 60.0 + (244.0-120.0)/2 = 122.0`)
- **?곌껐?좎쓽 y**: 移대뱶 ?몃줈 以묒떖?좎쓣 ?ъ슜?⑸땲?? ROW-A 湲곗? `y = 200.0 + 120.0/2 = 260.0`.
- **寃쎄퀎 洹쒖튃**: `y`??92.0 ?댁긽, `y + h`??500.0 ?댄븯?ъ빞 ?⑸땲?? ?뺥솗??`y = 92.0`,
  `y + h = 500.0`? **?⑸쾿**?낅땲?? ??踰붿쐞瑜?踰쀬뼱?섎㈃ ?뚮뜑留곸씠 嫄곕??⑸땲??

### 8.3. ?고듃 ?ш린 (??4媛쒕쭔 ?ъ슜)

| ??븷 | `size` | `bold` | `color` |
|---|---|---|---|
| ?뱀뀡 ?쒕ぉ (蹂몃Ц ?덉쓽 ?뚯젣紐? | 24 | `true` | INK |
| 蹂몃Ц (移대뱶 ?쒕ぉ, ?쇰컲 臾몄옣) | 18 | 移대뱶 ?쒕ぉ留?`true` | ?鍮?洹쒖튃???곕쫫 |
| 蹂댁“ ?ㅻ챸 | 14 | `false` | SECONDARY |
| 媛곸＜ | 12 | `false` | SECONDARY |

- **?щ씪?대뱶 ?쒕ぉ? ?ш린瑜?吏?뺥븯吏 ?딆뒿?덈떎.** 理쒖긽??`"title"` ?꾨뱶??臾몄옄?대쭔 ?ｌ쑝硫?
  ?쒗뵆由우씠 30pt濡??먮룞 ?뚮뜑留곹빀?덈떎. `elements` ?덉뿉 ?쒕ぉ ?띿뒪??諛뺤뒪瑜?留뚮뱾吏 留덉꽭??(짠3).
  ???쒖쓽 "?뱀뀡 ?쒕ぉ 24"??蹂몃Ц ?곸뿭 **?덉そ**???뚯젣紐⑹쓣 ?삵빀?덈떎.
- **湲瑗댁? ?좏깮?????놁뒿?덈떎.** ?뚮뜑?ш? Century Gothic + 留묒? 怨좊뵓??媛뺤젣 ?곸슜?⑸땲??
- **?먮룞 異뺤냼 ?놁쓬**: 湲?먭? ?곸옄蹂대떎 ?щ㈃ 洹몃?濡??섏묩?덈떎. ??244.0 移대뱶???ㅼ젣 ?띿뒪?????
  醫뚯슦 ?щ갚 7.2?⑹쓣 類 **229.6**?낅땲?? 18pt ?쒓? 湲곗? **??以???12??*濡?怨꾩궛?섍퀬, ?섏튂硫?
  以??섎? ?섎━吏 留먭퀬 臾몄옣??以꾩씠?몄슂.

### 8.4. ?뺣젹 諛?媛꾧꺽

- ?꾪삎(`rect`/`ellipse`/`triangle`) ?대? ?띿뒪?? `"align": "CENTER"`, `"valign": "MIDDLE"`.
- 臾몄옣???띿뒪??諛뺤뒪(`textbox`): `"align": "LEFT"`, `"valign": "MIDDLE"`.
- 媛숈? ?됱쓽 紐⑤뱺 移대뱶??`y`? `h`媛 **?꾩쟾???숈씪**?댁빞 ?⑸땲??
- `stroke`??湲곕낯?곸쑝濡??앸왂?섍굅??`null`?낅땲?? ?뚮몢由ш? 瑗??꾩슂???뚮쭔
  `{"color": "#6B727C", "width": 1.0}`???ъ슜?섏꽭?? `width: 0`? "???놁쓬"???꾨땲??
  **媛???뉗? ??*?대?濡??ъ슜?섏? 留덉꽭??
- `rotation`? ?ъ슜?섏? 留덉꽭??(??긽 0 / ?앸왂).
- ?붿냼 媛쒖닔??**3~9媛?*瑜??좎??섏꽭?? 洹??댁긽? ?щ씪?대뱶媛 ?쏀엳吏 ?딆뒿?덈떎.

### 8.5. 諛곗뿴 ?쒖꽌? id 洹쒖튃

- `elements` 諛곗뿴 ?쒖꽌: **??connector ????諛곌꼍/移대뱶 ?꾪삎 ?????띿뒪??諛뺤뒪** (짠2??Z-Index).
- `id`??`??낆빟???섎?_踰덊샇` ?뺤떇??snake_case濡? ?щ씪?대뱶 ?덉뿉??**以묐났 遺덇?**:
  `rect_step_1`, `txt_lead`, `conn_1_2`, `ell_core`, `tri_up`.

### 8.6. ?먭? ?먭? (異쒕젰 吏곸쟾 諛섎뱶???뺤씤)

1. 紐⑤뱺 ?됱긽??8.1??6媛??좏겙 ?덉뿉 ?덈뒗媛? (`#4472C4` ?놁쓬, 8?먮━ alpha ?놁쓬)
2. 紐⑤뱺 `x`/`w`媛 8.2?????쒖뿉 ?덈뒗 媛믪씤媛?
3. 紐⑤뱺 `y`/`h`媛 8.2?????쒖뿉 ?덈뒗 媛믪씤媛? (`y ??92.0`, `y + h ??500.0`)
4. 紐⑤뱺 `size`媛 24 / 18 / 14 / 12 以??섎굹?멸??
5. 紐⑤뱺 `run`??`t`, `size`, `color`媛 ?덈뒗媛? (怨듬갚 " " ?섎굹吏쒕━ run ?ы븿)
6. `elements` ?덉뿉 ?쒕ぉ???띿뒪??諛뺤뒪媛 ?녿뒗媛?
7. `target` ?꾨뱶瑜?異쒕젰?섏? ?딆븯?붽?? (?쒕쾭媛 二쇱엯?⑸땲??
````

---

## D. 짠5 and 짠7 must be brought into agreement ??same phase, same file

Per A6, this is load-bearing.

**D-a. `GEM_Knowledge_API.md:48`** ??replace `?뚯궗 釉뚮옖??鍮④컯 #E63312` with `?뚯궗 釉뚮옖??鍮④컯 #FF0032`, and adjust the alpha example so 짠5 documents the format while pointing at 짠8's narrowing (e.g. append `(?? AI ?앹꽦 異쒕젰?먯꽌??짠8.1???곕씪 alpha ?ъ슜 湲덉?)`).

**D-b. 짠7 Example 1** ??recolour and re-grid to the 3-column *flow* grid, columns 1 and 3:

| field | old | new |
|---|---|---|
| `circle_A` | `x 200, y 220, w/h 100`, `fill #0052CC` | `x 122.0, y 200.0, w 120.0, h 120.0`, `fill #FF0032` |
| `circle_B` | `x 660, y 220, w/h 100`, `fill #0052CC` | `x 718.0, y 200.0, w 120.0, h 120.0`, `fill #FF0032` |
| run size | 24 | 24 (unchanged), `color #FFFFFF` |
| `arrow_A_to_B` | `x1 300, y1 270, x2 660, y2 270, width 3.0` | `x1 242.0, y1 260.0, x2 718.0, y2 260.0, width 2.0`, `color #1A1A1A` |

*(check: 122 + 120 = 242; 718 + 120 = 838 ??900; centres 182 and 778 are symmetric about 480.)*

**D-c. 짠7 Example 2** ??re-grid to the 3-column *spaced* grid and fix the run size to the 8.3 scale:

| field | old | new |
|---|---|---|
| `box_1/2/3` `x` | 130 / 380 / 630 | **60.0 / 350.0 / 640.0** |
| `w`, `y`, `h` | 200, 200, 120 | **260.0**, **200.0**, 120.0 |
| `fill` | `#F4F5F7` | `#F4F5F7` (unchanged ??SURFACE) |
| run `size` | 20 | **18** |
| run `color` | `#1A1A1A` | `#1A1A1A` (unchanged ??INK on SURFACE) |

**D-d.** Optionally add a one-line pointer at the end of 짠7 (`???덉떆?ㅼ? 짠8??洹쒖튃??洹몃?濡??곕쫭?덈떎`) so the two sections are visibly coupled for the next editor.

---

## E. Scope and dispatch metadata for the next phase

```yaml
target_repo: C:\Users\2021670\Documents\硫???먯씠?꾪듃\tasks\AI_Powered_PPT
write_scope:
  - GEM_Knowledge_API.md          # the ONLY writable file
read_refs:
  - src/aippt/canvas/schema.json
  - src/aippt/canvas/geometry.py
  - src/aippt/canvas/style.py
  - src/aippt/canvas/validate.py
  - src/aippt/canvas/render_canvas.py
  - src/aippt/canvas/app.py
change_detail_path: <orchestrator's convention ??see caveat 3>
```

**Explicitly out of scope for this phase:** any `.py`, `.js`, `.json`, `.css` file; `GEM_Knowledge.md`; `Gemini_Web_Prompt.md`; `schema.json`. 짠8 is a *prompt-level* narrowing ??it must not be encoded as validation, or the human editor loses legitimate freedom (alpha, rotation, off-grid coordinates) that only the *AI author* is being restricted from.

---

## F. Acceptance criteria

1. `## 8. ?듭씪 ?붿옄???ㅽ???媛?대뱶 (STRICT TEMPLATE)` exists after 짠7, containing 8.1??.6.
2. `#E63312` no longer appears anywhere in `GEM_Knowledge_API.md`.
3. `#0052CC` no longer appears anywhere in `GEM_Knowledge_API.md`.
4. Every colour literal in the file is one of `#FF0032 #6B727C #F4F5F7 #1A1A1A #FFFFFF`, plus `#4472C4` and `#00000080` **only** where named as forbidden/illustrative.
5. Every `size` in 짠7 is one of 24 / 18 / 14 / 12.
6. Every `x`/`w` in 짠7 appears in an 8.2 column table; every `y`/`h` in a row table.
7. For every element in 짠7: `y ??92.0` and `y + h ??500.0` (connectors: both `y1`,`y2` in `[92, 500]`).
8. Neither 짠7 example emits a `target` field, and neither adds a title textbox.
9. No file other than `GEM_Knowledge_API.md` differs from HEAD.

**Verification.** Criteria 2?? are greps; 6?? are the arithmetic already tabulated above and can be checked by eye against the tables. If command execution is available, the strongest check is to load each 짠7 example, inject `target` from `reference/template_pin.json`, and call `aippt.canvas.validate.validate()` ??a clean return proves the examples are renderable. **Do not block on this:** command execution in these worker sessions is frequently gated behind an approval that never resolves; if so, state that in the change-detail and fall back to the table check rather than skipping verification silently.

---

## G. Mandatory follow-up (do NOT fold into this phase)

**Phase 1b ??propagate 짠8 to the Gemini web-paste path.** Copy the 짠8 block verbatim into `GEM_Knowledge.md` (as its own 짠8) and into `Gemini_Web_Prompt.md`, and replace `#E63312` in both (`GEM_Knowledge.md:46,70`; `Gemini_Web_Prompt.md:13,27`). **Until this ships, the user's stated goal ??Gemini and Sonnet producing identical design style ??is only half met.** `app.py:153-155`'s comment ("kept in one file so the two paths cannot drift") is currently inaccurate and should be corrected in a later, code-scoped phase.

---

## H. Assumptions and caveats

1. **`#FF0032` over `#0052CC` is a judgement call, not a fact.** The user's brief offered `#0052CC` as an example; I recommend `#FF0032` because it is the only red with code authority and a recorded user override (`renderer_brief.md:77-78`). Switching is a mechanical substitution in three places (짠5, 짠7, 짠8.1) ??but it must be all three or none.
2. **"Title = 24" was reinterpreted** as the in-body section heading (D-4). Taking it literally would require a title textbox, which 짠3 forbids and which produces a visibly duplicated title.
3. **`change_detail_path` is unspecified** in the source brief. This task has used at least three conventions (`phaseN_*_change_detail.md` at the repo root; `workers/<agent>/<NN-phase>/change_detail.md`; a flat `change_detail.md`). The next worker should follow whatever path its own dispatch frontmatter names, and file it in the **outer** tree even if `target_repo` points at a `.ma-stg/stg.*` staging worktree.
4. **Expect an `empty_diff_no_capture` report.** Stage diffs are taken with `git add -A` (no `-f`) against a `.gitignore` containing `tasks/*`; every `tasks/`-scoped phase in this project reports an empty diff regardless of what was written. Read the file to confirm the edit landed ??do not treat the empty diff as failure, and do not "re-apply" the edit in response to one.
5. **The 12-Korean-characters-per-line figure in 짠8.3 is an approximation** (229.6 pt usable width 첨 18 pt per full-width glyph), not a measurement. There is no autofit in the pipeline (`style.py:180`), so it is a budgeting heuristic for the model, not a guarantee.
6. **짠8 lengthens the system prompt on every generation.** The draft above is ~110 lines; that is the deliberate cost of determinism. Do not compress it by dropping the 8.6 self-check ??a terminal checklist is what actually converts prose rules into consistent output.
7. I did not execute any command (the one arithmetic-verification run I attempted was denied). All coordinate arithmetic in 짠C and 짠D was verified by hand and each result is shown inline so it can be re-checked without running anything.


## Additional Mandatory Follow-up
As per Section G in the WorkDirector's output, you MUST also apply these exact same §8 and color corrections to:
- \GEM_Knowledge.md\ (replace #E63312 and add §8)
- \Gemini_Web_Prompt.md\ (replace #E63312 and add §8)
