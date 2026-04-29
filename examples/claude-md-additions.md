## Vision MCP -- MANDATORY RULES
CRITICAL: You have two vision tools. You MUST use them for ANY image-related task. NEVER say "cannot view image" or "unable to view".
- `mcp__vision__see_image`: analyze an image file (absolute path). ALWAYS call this when Read is blocked on an image.
- `mcp__vision__see_clipboard`: analyze clipboard image. Use when user pastes/copies/screenshots but no image in message.
- Both accept optional `question` param.
- RULE: If Read is blocked for .png/.jpg/.jpeg/.gif/.webp/.bmp -> immediately call `mcp__vision__see_image` with the SAME path. No exceptions.
- RULE: If user pastes image but you see no image content -> call `mcp__vision__see_clipboard`.
- RULE: On 400 error after image paste -> ask user to save to file, then use `see_image`.

### Example: Read blocked on image -> use see_image
User: describe this image [pastes screenshot saved at /tmp/screenshot.png]
You try: Read("/tmp/screenshot.png") -> BLOCKED by vision-guard hook
CORRECT next action: call mcp__vision__see_image with {"image_path": "/tmp/screenshot.png"}
WRONG: saying "I cannot view images" or "let me try other methods" -- this is FORBIDDEN.

### Example: User pastes image but no image data visible
User: what does this show? [Image #1 but no visible content]
CORRECT: call mcp__vision__see_clipboard with {} or {"question": "what does this show?"}
