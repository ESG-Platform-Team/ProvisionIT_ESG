# Coding standards

How the team branches, commits, opens pull requests and reviews code. Every
change to `integration` or `main` follows this document. If something here
stops working for us, change it by pull request like any other file.

## 1. Branches

| Branch | Purpose | Who merges into it |
|---|---|---|
| `main` | What we demo and release. Always runs. | Only from `integration`, by pull request, at the end of a sprint |
| `integration` | Where finished work comes together and is tested | Feature branches, by reviewed pull request |
| `<type>/<description>` | One piece of work, short-lived | The owner pushes; nobody else commits without asking |

Start every branch from the latest `integration`:

```
git checkout integration
git pull
git checkout -b feature/pdf-report-email
```

### Naming

`<type>/<short-description>`, lowercase, words joined by hyphens.

| Type | Use for |
|---|---|
| `feature/` | New behaviour a user or the client can see |
| `fix/` | A bug fix |
| `docs/` | Documentation only |
| `test/` | Tests only |
| `refactor/` | Restructuring with no change in behaviour |
| `chore/` | Tooling, CI, dependencies, config |

Add the Jira key when there is one: `feature/ESG-42-pdf-report-email`.

Good: `feature/disclosure-requests`, `fix/report-unicode-dash`, `docs/deployment-plan`
Not: `jun-backend-adapter`, `matrix_and_scoring`, `test2`, `agam-changes`

Branches created before this document (`jun-backend-adapter`,
`matrix_and_scoring`, `feature/crawl_extract`) keep their names until they are
merged or deleted. New branches use the convention.

Delete a branch once its pull request is merged.

## 2. Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary in the imperative, 72 characters or fewer>

<body: what changed and why, wrapped at 72 characters>

<footer: Jira key, Co-authored-by lines>
```

- **type** is one of `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- **scope** is the area touched: `scoring`, `harvest`, `pipeline`, `api`,
  `report`, `mailer`, `disclosure`, `frontend`, `ci`.
- The summary says what the commit does, not what you did: "add PDF report",
  not "added PDF report" or "PDF stuff".
- One logical change per commit. Formatting-only changes get their own commit.

Example:

```
feat(report): render assessments as a branded PDF

Adds report.render(), which produces a cover page with every pillar,
a page per pillar with quoted evidence and page numbers, and the source
log. The machine interpretation statement is printed on the cover.

Refs: ESG-42
Co-authored-by: Agam Johal <agam@student.unimelb.edu.au>
```

If someone else wrote part of the change, or it was produced with an AI
assistant, say so with a `Co-authored-by:` line. The history should show who
made what.

## 3. Pull requests

- **Target `integration`**, never `main` directly.
- **Keep it focused.** One feature or fix per pull request. Aim for something a
  reviewer can read in 30 minutes.
- **Fill in the template.** It asks what changed, why, how it was tested and
  which Jira ticket it closes.
- **Tests pass before you ask for review.** Run them locally (section 5), and CI
  must be green.
- **Add a line to `CHANGELOG.md`** under *Unreleased*.
- **Screenshots** for anything that changes the interface.
- **No secrets.** No API keys, passwords or `.env` files, ever. If one is
  committed by accident, rotate it immediately; deleting the commit is not
  enough.

## 4. Review

- **Every pull request needs one approval from someone other than the author**
  before it is merged. Nobody approves or merges their own work.
- The reviewer is named in the pull request. Review within one working day, or
  say when you can.
- Review for: does it do what the ticket says; are the tests meaningful; is it
  readable; does it keep the scoring rules (two scores never averaged, five
  disclosure states, source grade separate from score, no zero for missing
  evidence); any secrets or personal data.
- Leave comments on the lines concerned. Use "Request changes" for anything
  that must be fixed, "Comment" for suggestions.
- The author resolves every conversation, then the reviewer approves.
- **Merge with "Create a merge commit"** and delete the branch. (Not squash: our
  branches are often stacked on each other, and squashing breaks the next one.)

## 5. Code and tests

Python (backend):

- Python 3.11. Lint with ruff using `backend/ruff.toml`:
  `cd backend && ruff check .`
- Every module starts with a docstring saying what it is for.
- Scoring stays deterministic. The language model reads and quotes; code
  decides every status, score, band and grade.
- Every change in behaviour comes with a test in a `backend/test_*.py` file.
  Tests run offline: no network, no API key, no cost.

Run everything before you push:

```
cd backend
for t in test_*.py; do python "$t" || exit 1; done
ruff check .
```

JavaScript (frontend):

- No build step. `frontend/backend.js` is the only file that talks to the API.
- Test changes in the browser with `./demo.sh --reset` against the fixture
  company (TST) before asking for review.

## 6. Definition of done

A change is done when:

1. It is merged into `integration` through a reviewed pull request.
2. CI is green.
3. Tests cover the new behaviour.
4. `CHANGELOG.md` and any affected document (README, DEMO, Confluence) are
   updated.
5. The Jira ticket is moved to Done with a link to the pull request.

## 7. Repository settings (admin)

On GitHub, Settings > Branches > Add branch ruleset, for both `main` and
`integration`:

- Require a pull request before merging, with 1 approval
- Dismiss stale approvals when new commits are pushed
- Require status checks to pass: `tests`
- Block force pushes and deletion
