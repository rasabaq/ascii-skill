# Contributing

Thanks for helping. Small, focused changes are easiest to review.

## Run the tests

You need [uv](https://docs.astral.sh/uv/). ffmpeg is needed for video tests. Each test is a script that installs Pillow by itself:

```
for t in tests/test_*.py; do uv run $t || echo FAIL $t; done
```

All five take about 10 seconds together. None of them use the network.

## The one rule

Keep it small: Python 3.9+ and Pillow only (ffmpeg is optional, for video). Do not add a new Python dependency. Each script lists its dependencies in its PEP 723 header, so `uv run` works with no setup.

Also: if you add or change an option, update `skills/ascii-art/SKILL.md` and add a test in the matching `tests/test_*.py`.

## Open a pull request

1. Fork the repo and make a branch.
2. Make your change and run the tests.
3. Open a pull request against `main`. Say what changed and why. Add a before/after picture if the output looks different.

CI runs the same tests on Python 3.9 and 3.12.
