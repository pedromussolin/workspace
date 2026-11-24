# Jira

What is specific to Jira in the `/card` flow. Read it when the tracker in `config.toml` is Jira.

- **Setup (exit 2):** a `[tracker.jira]` key missing in `config.toml` (an old `[jira]` table still
  works, and the message then names it), or no API key. The user runs `ws config token jira` in
  their own terminal, outside Claude, or fills `config.toml` (README, "Local config"). The site
  must be `https://<name>.atlassian.net`.
- **Prompt:** the confirmation on the user's terminal prints exactly `Gravar no Jira? [s/N]`.
- **Start date:** when the card has no start date to set, `[tracker.jira] start_date_field` (or
  `start_date_field` of an old `[jira]` table) is missing in `config.toml`.
- **Epic and initiative:** `[tracker.jira] premium` (default `false`) says whether this Jira has the
  premium plan. Without it an epic cannot have an initiative as its parent, so `parent` on an epic
  `edit` adds the link `[tracker.jira] initiative_link` names (a key of `[tracker.jira.links]`,
  default `relates`), shown in the preview as `Iniciativa: TS-N (por link Relates)`; a link already
  there, either way, changes nothing (the plan shows `Iniciativa: TS-N (por link Relates): já
  existe`). That edit holds `parent` alone: with any other change it is refused, so the other
  changes go in another draft, in the same batch if wanted (one preview, one approval).
- **New epic with an initiative, without premium:** two steps. Create the epic without `parent`
  (a create with `parent` is refused: the link needs the new card's key), then edit it with
  `parent`.
- **Epic screens, with `premium = true`:** `parent` sets the parent field; when this Jira's epic
  create or edit screen has no `parent`, the check refuses it and the user links the epic to its
  initiative by hand, in Jira.
- **Labels, original estimate and `causes`:** `labels` (create), `add_labels` and `remove_labels`
  (edit, never a replace of the whole list) need `labels` on the type's create screen and the card's
  edit screen; the check names the screen that lacks it. `estimate` goes in the create when the
  create screen has the original-estimate field (`timetracking`); this Jira's create screen does not,
  so a create sends it in a second request right after the card is made, under the same approval,
  and when only that second request fails the report says the card was created and the estimate was
  not applied (set it with an edit). `causes` and `caused_by` map to the link type
  `[tracker.jira.links] causes` names (`ws tracker discover` fills it).
- **Card policy:** the title format, the sections of each type, the required fields, the
  categories and the done rules come from the card policy (`ws card policy`), not from the
  tracker adapter; a setup error in a policy file (a missing company file, an invalid layer) exits 2
  with the file in the message.
- **Uncertain result on a `create`:** offer the JQL (Jira's search syntax) to look for the title,
  for example `project = TS AND summary ~ "<title>"`.
- **Refusals:** a write to another person's card or another project is refused; a field missing
  from the type's create screen or the card's edit screen is named by the check.
- **Never use the Atlassian MCP to write.** Nothing is written through it, ever.
