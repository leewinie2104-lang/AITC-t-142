# Jira ticket rules

Applies whenever you create, edit, move or close a Jira ticket for ParkSmart
(site `nminhphucnmp0512.atlassian.net`, project `SCRUM`). Ticket text is Vietnamese; this rule is English.

## Before creating

- Search first (JQL on summary/text). If a ticket already covers the work, update it instead of creating a duplicate.
- Create only what the user asked for. Show the planned list (summary + epic + sprint) when it is more than 3 tickets.
- Never put secrets, API keys, account passwords, personal emails or other PII in a ticket.

## Summary (title)

- An overview of the outcome a reader gets at a glance in the board, not the steps: `[Area] <what exists / works when done>`.
- Area prefix matches the board: `[Infra]`, `[Booking]`, `[Agent]`, `[Demo]`, `[Docs]` … reuse an existing prefix before inventing one.
- ≤ 80 characters, no ending period, no ticket key, no dates. Put the plan step only if it helps: `… — plan 015 bước 5a`.
- Good: `[Infra] Runner CI riêng trên EC2 (label p142)`. Bad: `Tạo EC2, gắn role, cài docker, đăng ký runner`.

## Description

Describe the work to do, in this order (skip a section only if it is empty):

1. **Mục tiêu**: 1–2 sentences on why and the expected result.
2. **Việc cần làm**: a bullet list of concrete tasks (files, resources, commands). Use plain `-` bullets: `- [ ]` is escaped
   by the Markdown converter and shows as text.
3. **Done khi**: verifiable acceptance checks (command, URL, test name, status on a page).
4. **Phụ thuộc / chờ**: blockers and who must act (BTC, user approval, another ticket key).
5. **Liên quan**: plan file, ADR, BR-xx / AC-xx, related ticket keys, repo paths. Link, do not copy their content.

Keep it under ~25 lines; long detail belongs in the plan or runbook it links to. Mention cost when the work creates paid resources.

## Fields

- **Type**: `Task` by default; `Bug` for defects; `Epic` only when the user asks. Always set the parent epic.
- **Labels**: priority (`P1`/`P2`/`P3`) + area (`infra`, `agent`, …) + `psa`, copying what sibling tickets in the epic use.
- **Assignee**: the user (`atlassianUserInfo`) unless told otherwise. **Priority**: `High` if it blocks the sprint goal.
- **Sprint**: work starting now → the current sprint by numeric id (`"active"` matches several sprints); later work → backlog.
  Do not move tickets into or out of a sprint, or change the sprint goal, without the user's go-ahead.

## Status

- To Do → **In Progress** when work starts (files being written count), **In Review** when the PR is open,
  **Done** after merge and the "Done khi" checks pass.
- No "Won't Do" status exists. To cancel: comment the reason and the replacing ticket, prefix the summary with
  `[Hủy, thay bởi SCRUM-NNN]`, move it to the backlog, then set Done, so it does not count toward sprint velocity.
- After changing status, report the old → new status for every ticket touched.

## Linking with git

- Branch: `<type>/scrum-<key>-<short-slug>` off `dev` (e.g. `feat/scrum-177-lightsail-deploy`). Use a key that exists on this site.
- PR title: Conventional Commit with the ticket key at the end, e.g. `feat(infra): deploy image to ECR via OIDC (SCRUM-177)`.
- Keep the plan's **Refs** line and the ticket's **Liên quan** pointing at each other.
