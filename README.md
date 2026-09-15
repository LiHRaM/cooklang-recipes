# cooklint

A small linter for the Cooklang recipe files in this repo. It catches the
mistakes that make recipes render oddly or break in the Cooklang mobile app:

| Check | Severity | Why it matters |
|-------|----------|----------------|
| Timer has no unit (`~simmer{25}`) | error | App shows a 0-minute timer |
| Timer value is a range (`~{20-25%minutter}`) | error | App can't time a range |
| Timer uses a non-canonical unit (`minutter`/`timer`/`min`) | error | App resolves these to 0 |
| No blank line between direction lines | warning | App merges them into a single step |
| No `servings:` declaration | warning | App can't scale ingredient amounts |

## Usage

Run against the whole `recipes/` tree without installing anything:

```sh
uv run --project . cooklint recipes
```

Point it at one or more files too:

```sh
uv run --project . cooklint "recipes/Baking/Shower Buns.cook"
```

Exit code is `0` when there are no findings, `1` otherwise. Use `--quiet` to
suppress the end summary.

## How it stays stable

cooklint is a pure-stdlib regex linter. It does not depend on a Cooklang
parser, because parser libraries disagree on what a timer's quantity looks
like across versions (some expose a pre-parsed `Quantity`, others a raw
string). The checks here are written directly against the Cooklang spec and
the mobile app's behavior, so results do not change when the parser churns.

## Adding a checklist to the app

Shower Buns.cook is the reference recipe: canonical English units
(`20%minutes`, `18%minutes`), a `servings:` header, and a blank line between
every direction step. Keep new recipes to that shape and cooklint stays green.
