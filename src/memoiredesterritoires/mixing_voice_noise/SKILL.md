---
name: mixing_voice_noise
description: Mix voice with noises using intelligent parameter selection
when_to_use: "User wants to add background noise to voice recording"
---

## Instructions
1. When the user wants to add background noise to a voice recording, gather the following details:
   - `voice_file_path`: Path to the voice recording file.
   - `noise_file_paths`: List of paths to noise files to be mixed with the voice.
   - `mixing_parameters`: Any specific parameters for mixing (e.g., volume levels, duration). 
2. Call the `mix_voice_noises` tool with the collected details.
3. Summarize the mixing process, including the files used and any parameters applied.
4. Provide the user with the path to the resulting mixed audio file.
5. If there are any issues during mixing, clearly state the problem and suggest possible solutions.

## Example
```