# P023 browser access diagnosis — 2026-11-05

The user confirmed option 1 for the four run004 UI checks and separately requested diagnosis and repair of the browser tool restriction. The human UI observation is recorded independently; it is not Codex UI verification or whole-packet ground-truth approval.

## Evidence and conclusion

The preserved P021 failure (`docs/verification/p021/README.md`) reports: “requested URL protocol is not allowed. Allowed protocols: http:, https:”. Both navigation and reading an already-open file URL were blocked in the earlier session. This identifies the observed blocker at the browser tool URL-policy layer, before report rendering; it does not demonstrate a defect in the HTML or filesystem permissions.

This turn read the current CUA API documentation, the selected IAB documentation, and its `browser-troubleshooting` and `local-web-development` guidance. These expose browser observation/control and ordinary local web testing, but no supported operation to change the file-protocol restriction. The blocked navigation was not repeated.

The official [Browser documentation](https://learn.chatgpt.com/docs/browser), fetched this turn, describes browser UI inspection and local web-app preview. It also distinguishes manual file-backed preview from browser automation and says managed environments may restrict browser access. It does not establish a supported file-protocol policy override for this session, nor prove an administrator setting caused this specific failure.

Status: cause localized; restriction NOT repaired. Browser automation exists, but that does not establish access to this particular file URL. No permission/configuration changes, alternate browser control surface, raw CDP, temporary HTTP server, file publication, model call or download was attempted. The tool restriction cannot be declared fixed using HTML structural tests or the user's observation. A supported tool-provider resolution is needed before claiming direct verification of this blocked target.
