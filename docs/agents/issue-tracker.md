# Issue tracker

Issues and specs live in GitHub Issues: eduNEXT/eox-redsys.
Use the gh CLI from this repository.

- Read: `gh issue view <number> --json number,title,body,labels,comments`
- List: `gh issue list --state open`
- Create: `gh issue create --title "..." --body-file <file>`
- Label: `gh issue edit <number> --add-label "..."`
- Comment: `gh issue comment <number> --body-file <file>`
- Close: post the explanation, then `gh issue close <number>`.

Before creating an issue, verify the target with:
`gh repo view --json nameWithOwner`

Link child tickets to their parent using GitHub sub-issues.
When unavailable, write `Part of #<parent>` in the child.
Represent blockers using native issue dependencies, falling back
to a `Blocked by: #<number>` line when unavailable.

PRs as a request surface: no.

Publishing to the issue tracker means creating a GitHub issue.
Fetching a relevant ticket means reading its issue and comments.
