---
name: architecture-documentation
description: Write architecture documentation for a software repository. Use when asked to document, describe, or explain the architecture, structure, or design of a codebase.
---

# Architecture documentation

When asked to document the architecture of a repository:

1. Find existing architecture documentation first. Check `docs/`, `README.md`,
   `CONTRIBUTING.md`, and any ADRs, and note where the project says such
   documentation should live.
2. Identify the main components of the application and how they interact.
3. If an architecture document already exists, check it against the current
   code. If it is stale, rewrite it in place rather than creating a second
   document. Otherwise create one in the location the project's conventions
   indicate (default: `docs/architecture.md`).
4. Write a Markdown document describing the components, their responsibilities,
   and the data flow between them. Keep it to roughly 80 lines: a component
   list, responsibilities, and a short data-flow description are sufficient.
   Link to existing ADRs instead of restating them.
5. Keep the document accurate to the code that actually exists.
6. If other files (for example a README "Architecture" section) describe the
   architecture in a way that now contradicts your document, update them so the
   repository does not contain conflicting descriptions. Do not modify source
   code for a documentation task.
7. In your final message, say which files you rewrote and which you created.
