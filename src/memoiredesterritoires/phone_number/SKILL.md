---
name: french-phone-formatter
description: Format and analyze French phone numbers (04 landline & 06 mobile) with cultural context for each digit pair
---

# French Phone Formatter

## Instructions
1. Take a French phone number as input (04 or 06 prefix)
2. Identify if it's a landline (04) or mobile (06)
3. Break the number into pairs of digits
4. For each pair, provide what that number is culturally known for in France
5. Return the result as JSON format with:
   - `type`: "landline" or "mobile"
   - `formatted`: the number in pairs (e.g., "04 12 34 56 78")
   - `analysis`: array of objects with `pair` and `meaning`

## Examples

**Example 1:**
Input: `0412345678`
Output:
```json
{
  "type": "landline",
  "formatted": "04 12 34 56 78",
  "analysis": [
    {"pair": "04", "meaning": "Southeast France region code"},
    {"pair": "12", "meaning": "The number 12 - months in a year, dozen"},
    {"pair": "34", "meaning": "Department number of Hérault"},
    {"pair": "56", "meaning": "Department number of Morbihan in Brittany"},
    {"pair": "78", "meaning": "Yvelines department, home to Versailles"}
  ]
}
```

**Example 2:**
Input: `0623456789`
Output:
```json
{
  "type": "mobile",
  "formatted": "06 23 45 67 89",
  "analysis": [
    {"pair": "06", "meaning": "Mobile phone prefix in France"},
    {"pair": "23", "meaning": "The number 23 - Michael Jordan's jersey"},
    {"pair": "45", "meaning": "Number of seconds in 3/4 of a minute"},
    {"pair": "67", "meaning": "Bas-Rhin department in Alsace"},
    {"pair": "89", "meaning": "Yonne department in Burgundy, year of French Revolution bicentennial"}
  ]
}
```