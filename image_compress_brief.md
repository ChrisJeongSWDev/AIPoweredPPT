---
mode: edit
claude_model: sonnet
target_repo: c:/Users/2021670/Documents/멀티 에이전트
write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js
change_detail_path: tasks/AI_Powered_PPT/image_compress_change_detail.md
approved_write_manifest: tasks/AI_Powered_PPT/image_compress_manifest.txt
---

# Task Description
The user wants to compress and resize imported images on the client side before they are stored or exported. This prevents large images from exhausting the 2MB HTTP payload limit (`MAX_BODY_BYTES`) during export to PPTX, while avoiding the need to relax the server's protection limits.

## Instructions
1. Open `tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js`.
2. Implement a new asynchronous function `compressImage(file)` that takes an `image/*` File object.
   - It should read the file into an `Image` object.
   - It should create an off-screen `<canvas>`.
   - If the image exceeds `1920x1080` in either dimension, calculate a scaled-down size while preserving aspect ratio. Otherwise, use the original dimensions.
   - Draw the image onto the canvas at the calculated size.
   - Call `canvas.toBlob` with `image/jpeg` and a quality of `0.8`.
   - Return the resulting Blob as a new `File` object (give it a `.jpg` extension if needed, or just return the Blob to be registered).
3. Modify the existing `mediaInputHandler(type)` function:
   - If `type === 'image'`, instead of calling `insertMedia(type, file)` directly, pass the file to `compressImage(file)`.
   - Await the compressed file (or use `.then()`), and then call `insertMedia(type, compressedFile)`.
   - If `type === 'video'`, do not compress it; just call `insertMedia(type, file)` directly.
4. Ensure the UI still shows "Added image X." properly and that no functionality is broken. Remember `mediaInputHandler` is bound to the `<input type="file">` change event, so handling the async flow cleanly is important.

Document your changes in `tasks/AI_Powered_PPT/image_compress_change_detail.md`.
