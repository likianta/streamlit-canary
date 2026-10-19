# Components V2 (Broken)

Components V2 was a transitional implementation between the original
Streamlit-based components and the event-driven V3 library. It explored a
reactive property model, but it was never finished and is **not
maintained**.

The module is still importable as `sc.v2` so that old experiments do not
fail at import time, but:

- its behavior is not guaranteed;
- it does not receive fixes;
- it is not covered by this manual.

Do not start a new app with V2. Use [Components V3](../components-v3/index.md)
instead. If you have an app written against V2, the V3 API is close enough
that porting it is usually a mechanical change.
