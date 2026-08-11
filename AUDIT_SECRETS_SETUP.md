# AUDIT SECRETS SETUP RUNBOOK

## Objective
Securely provision the PyPI API Token for automated `manimgl-lite` GitHub Action deployments.

## Procedure
1. **Generate PyPI Token**
   - Log into [PyPI.org](https://pypi.org/).
   - Navigate to Account Settings > API Tokens.
   - Select "Add API Token", restrict the scope to the `manimgl-lite` project if it exists (or leave open for first publish), and generate the token.

2. **Inject Secret to GitHub**
   - Navigate to your repository on GitHub: `madhun2319/manimgl-lite`.
   - Go to **Settings** > **Secrets and variables** > **Actions**.
   - Click **New repository secret**.
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: Paste the generated `pypi-...` token exactly.
   - Click **Add secret**.

## Authorization Mapping
The GitHub Action `.github/workflows/publish.yml` reads this token via `${{ secrets.PYPI_API_TOKEN }}`. Without this, the Twine upload step will be completely blocked, enforcing tight continuous deployment security.
