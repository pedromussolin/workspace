# Jira

What is specific to Jira in the `/card` flow. Read it when the tracker in `config.toml` is Jira.

- **Setup (exit 2):** a `[jira]` key missing in `config.toml`, or no API key. The user runs
  `ws config token jira` in their own terminal, outside Claude, or fills `config.toml` (README,
  "Local config"). The site must be `https://<name>.atlassian.net`.
- **Prompt:** the confirmation on the user's terminal prints exactly `Gravar no Jira? [s/N]`.
- **Start date:** when the card has no start date to set, `[jira] start_date_field` is missing in
  `config.toml`.
- **Epic screens:** this Jira's epic create and edit screens have no `parent`, so the check refuses
  it and the user links the epic to its initiative by hand, in Jira.
- **Uncertain result on a `create`:** offer the JQL (Jira's search syntax) to look for the title,
  for example `project = TS AND summary ~ "<title>"`.
- **Refusals:** a write to another person's card or another project is refused; a field missing
  from the type's create screen or the card's edit screen is named by the check.
- **Never use the Atlassian MCP to write.** Nothing is written through it, ever.
