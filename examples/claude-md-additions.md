## Vision MCP (image analysis)
Two vision tools are available via MCP for image analysis:
- `mcp__vision__see_image`: analyze an image file on disk (absolute path, PNG/JPG/JPEG/GIF/WEBP/BMP, max 20MB)
- `mcp__vision__see_clipboard`: analyze the image currently in the system clipboard
- Both accept an optional `question` param -- omit for thorough description, or pass a specific question
- If Read tool is blocked for an image file (vision-guard hook), use `see_image` with the same path
- If a user mentions pasting/copying/screenshotting but you see no image content in the message, use `see_clipboard`
- If you receive a 400 error after a user pastes an image, the image content block may be unsupported -- ask the user to save the image to a file and use `see_image`, or try `see_clipboard`
