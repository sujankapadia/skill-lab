# Interactive example: sow-draft

`sow-draft` is a real skill that gathers ~12 parameters through
`AskUserQuestion` rounds and then runs a generator to produce a `.docx`. It
cannot run headless — nobody answers — so it exercises Skill Lab's interactive
mode, where a second Claude Code instance plays the user from `persona-acme.md`.

The skill itself is not vendored here (it lives in the chariot-skills plugin);
point `--skill` at its directory:

```bash
uv run skill-lab run --interactive \
  --skill ~/.claude/plugins/marketplaces/chariot-marketplace/plugins/chariot-skills/skills/sow-draft \
  --repo ./examples/sow-draft/workspace \
  --persona-file ./examples/sow-draft/persona-acme.md \
  --apt python3-docx \
  --attempts 20 --concurrency 4 --name sow-v1
```
