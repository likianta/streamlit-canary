# Roadmap

This page lists the work that is currently planned for Streamlit Canary.
It is indicative rather than a promise, and the order may change.

## V3 stabilization

- Finish the remaining widget parity with Streamlit.
- Replace the leftover V2 internals that V3 still shares.
- Harden the patch protocol and reconnect / resync behavior.
- Add more automated tests for the runtime, the renderer, and the trees.

## API consolidation

- Port Streamlit's chart elements to V3.
- Remove (or downgrade) V1, remove V2 entirely, and drop the `v3` prefix
  so the V3 components become the default `sc.*` API.

## Documentation

- Complete the API reference for every V3 component.
- Add a migration guide for larger real-world apps.
- Publish runnable examples for the most common layouts and widgets.

## Developer experience

- Improve error messages when a component is used outside a valid parent.
- Document the sizing and visibility rules in one place.
- Provide a small project template that can be copied to start a new app.

## Packaging and release

- Keep the published package in step with the repository.
- Add a `LICENSE` file and make the license visible on GitHub.
- Automate the release checklist (tests, version bump, changelog, tag).

## Applications

- Rewrite a few third-party Streamlit apps with V3 components to validate
  the API against real use cases.
- Publish the rewritten apps as reference implementations.
