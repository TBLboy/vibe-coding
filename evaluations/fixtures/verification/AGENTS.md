# Approved rules
- Task starts in `prepare`; only prepare → implement → verify → complete is legal.
- Invalid transitions raise ValueError, leave stored state unchanged, and do not increment the write counter. Terminal state is immutable.
- Test the actual `handle` entrypoint. For this exercise, design and run tests only; do not fix production files.
