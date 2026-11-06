---
description: Maintain the separate learner and contributor portals, preview both, and publish them with GitHub Pages.
---
# Maintain this documentation

PreparationPalAI has two MkDocs portals in one GitHub Pages site:

| Audience | Source | Configuration | Published path |
| --- | --- | --- | --- |
| Learners | `docs/` | `mkdocs.yml` | `/PreparationPalAI/` |
| Contributors and operators | `engineering/` | `mkdocs-contributors.yml` | `/PreparationPalAI/contribute/` |

They share branding through `mkdocs.base.yml` and `docs_theme/`, but each has its
own navigation and search index. The learner search must not turn into an API or
deployment reference.

## Write for the right audience

For the **product guide**, start with the task: what someone is trying to learn,
which control to use, what they should expect, and what to do if it fails. Use
the visible labels from the UI. Keep limitations concrete. Do not claim exam
outcomes, complete syllabus coverage, or model accuracy that has not been evaluated.

For the **contributor handbook**, explain setup, architecture, contracts, tests,
configuration, and operations. Keep secrets and private study material out of examples.
If a product page needs implementation detail to make sense, simplify the page or
link here for the administrator’s part of the task.

## Build and preview

```bash
pip install -r requirements-docs.txt
python scripts/build_docs.py --preview --port 8088
```

Open `http://localhost:8088/PreparationPalAI/` for the product guide and
`http://localhost:8088/PreparationPalAI/contribute/` for the handbook. This preview
preserves the GitHub project path, including links between the portals. To build
without starting a server, run `python scripts/build_docs.py`.

The build runs product first and handbook second. Do not rebuild the product alone
after the combined build when preparing a deployment: MkDocs cleans its output
directory, which would remove the handbook nested inside it.

## Theme and content structure

- Add product pages to `mkdocs.yml` and engineering pages to `mkdocs-contributors.yml`.
- Shared typography, colour, cards, and responsive rules live in the brand stylesheet.
- Custom templates add the product homepage, social metadata, and audience links.
- Fonts use the system stack; search assets are hosted with the site. There is no
  analytics integration or external font request.
- Use descriptive page metadata and normal relative Markdown links within each portal.

## Publish

The Pages workflow builds and validates on pull requests. It publishes from `main`
and explicit manual runs. The initial `feat/preparation-coach` publication is allowed
only while `main` has no MkDocs configuration; after merge, that bootstrap branch
cannot overwrite the main documentation. It uses
GitHub’s Pages artifacts and deployment actions rather than uploading app data.
The site is static documentation; it does not host the FastAPI study application.

Changes in navigation, theme, or the build script need a browser check of search,
dark mode, mobile menus, and cross-portal links before publishing.
