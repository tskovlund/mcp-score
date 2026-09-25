# Security policy

## Supported versions

Only the latest 0.x release receives security fixes. Upgrade before reporting.

## Reporting a vulnerability

Please do not open a public issue. Report privately through
[GitHub private vulnerability reporting](https://github.com/tskovlund/mcp-score/security/advisories/new)
or by email to [thomas@skovlund.dev](mailto:thomas@skovlund.dev).

You can expect an acknowledgement within a week. Confirmed issues are fixed in
a patch release, and the advisory is published once the fix is out.

## Scope

`generate_score` runs the Python script the AI assistant writes, on the user's
machine, with the user's privileges. That is the feature, not a vulnerability:
the tool exists so that a music21 script can produce a score file. Use an MCP
client that lets you review tool calls before they run, and only connect
assistants you trust.

Reports about the MuseScore plugin's WebSocket server are in scope. It listens
on `localhost` only and accepts commands without authentication, so anything
that could reach it from another host, or escape the score it operates on,
is worth reporting.
