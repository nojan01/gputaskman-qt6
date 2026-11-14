# Automated CI

The release was validated locally and on the primary target operating systems;
see VALIDATION.md. A ready-to-use GitHub Actions workflow is provided in
`docs/ci-workflow.yml`.

It is **not enabled** in the initial public repository: the connected GitHub
integration rejected creation of `.github/workflows/ci.yml` with HTTP 403
(Resource not accessible by integration), and the available CLI credential does
not include workflow-write scope. No green GitHub Actions result is claimed.

To enable CI, copy that template to `.github/workflows/ci.yml` using a credential
with permission to create/update workflows. It builds the collector, runs the
GUI/identity/fleet/refresh tests, and exercises 4/8/16-card synthetic demos.
It does not publish binary releases automatically.
