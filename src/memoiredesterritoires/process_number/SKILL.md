---
name: process-number
description: When user asks for a number to be processed, use the process_number tool to multiply it by 2
---

# Process Number

## Instructions
1. When user asks to process a number, extract the number from their request
2. Call the `process_number` tool with the number as parameter
3. Return the result clearly

## Examples

**Example 1:**
User asks: "Can you process number 324?"
Response:
```
[Calls process_number tool with num=324]
Processing number 324...
Result: 648
```

**Example 2:**
User asks: "Process 50 for me"
Response:
```
[Calls process_number tool with num=50]
Processing number 50...
Result: 100
```

## Tool Details
- Function: `process_number(num: int) -> int`
- Action: Multiplies the input number by 2
- Location: `src/memoiredesterritoires/process_number/process_number.py`