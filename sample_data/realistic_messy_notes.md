# Realistic Messy Dataset Notes

This dataset is meant to stress-test the intake layer more than the diagnosis layer.

It intentionally includes:

- semicolon delimiters
- alternate header names
- percentage-style rate fields
- currency symbols
- decimal commas
- one row missing `ASIN`
- one row missing `title`

Use it to check:

1. whether the file loads cleanly
2. whether invalid rows are rejected with visible reasons
3. whether header mapping is shown correctly
4. whether the diagnosis still feels believable on less-clean input
