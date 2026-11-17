# Tracker reference: jira

Used by step 3 of the daily when `[tracker] kind` is `jira`. Read only: never call a write tool.

- Read `[tracker.jira] site` from `~/.config/workspace/config.toml`, or `[jira] site` when there
  is no `[tracker.jira]` table. Call `getAccessibleAtlassianResources` and take the `cloudId` of
  the resource whose `url` equals that site. No config file, no matching resource or an MCP error: there are **no cards**, see the
  end of this file.
- Call `atlassianUserInfo` for the account id (used only to set `reporter_is_me`).
- Call `searchJiraIssuesUsingJql` with `cloudId`, `maxResults: 100`,
  `fields: ["summary", "status", "parent", "reporter", "updated", "issuetype", "statuscategorychangedate", "resolutiondate"]`
  and this `jql`:

  ```text
  assignee = currentUser() AND (statusCategory != Done OR updated >= "<since>") ORDER BY updated DESC
  ```

- The answer is `issues.nodes[]` and `issues.pageInfo`. While `hasNextPage` is true, call again
  with `nextPageToken` set to `endCursor`.
- Turn each node into a compact card with exactly these fields: `key`; `title`
  (`fields.summary`); `status_name` (`fields.status.name`); `status_category`
  (`fields.status.statusCategory.key`: `new`, `indeterminate` or `done`); `epic_key` and
  `epic_title` (`fields.parent.key` and `fields.parent.fields.summary`, `null` without a
  parent); `reporter_is_me` (`fields.reporter.accountId` equals the account id);
  `updated` (`fields.updated`, as it came); `is_epic` (`fields.issuetype.hierarchyLevel >= 1`,
  true or false, whatever the type's name); `status_changed` (`fields.statuscategorychangedate`)
  and `resolved` (`fields.resolutiondate`), as they came, `null` when absent.
- Create `~/.local/share/workspace/standup/cards.json` with the Write tool (not an inline shell
  string, so titles need no quoting), containing `{"platform": "jira", "cards": [...]}`. When
  the Write tool is denied, write the same JSON with a quoted heredoc
  (`cat > ~/.local/share/workspace/standup/cards.json <<'EOF'` ... `EOF`): the quotes around
  `EOF` keep the shell from touching the titles. Never drop the fetched cards because Write
  was denied.

With no cards (no match, no config or an MCP error), the daily goes to step 4 without `--cards`.
