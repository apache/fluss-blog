# Reproducing the retry lab

The current portable setup has not been verified. The article's recorded results belong to the historical run described below.

Download the [public reproduction archive](public-reproduction-fluss-v3.tar.gz), [setup and cleanup guide](public-package/REPRODUCE.md), and [package manifest](public-package/PUBLIC_MANIFEST.json). The archive contains the complete package. Extract it into a fresh directory using the guide; the website provides the guide and manifest separately for inspection.

SHA-256 pins:

```text
public-reproduction-fluss-v3.tar.gz
cb45a7dd9ceb12e1647755e28f3d87aeabf0b999d0e76a3efa49938fe6458ea1

PUBLIC_MANIFEST.json
9696fe1189c197a174a94647440b6fb7c9b82536256bf129e7a6bcc4f14e6765
```

The guide covers allocation limits, build, execution, independent export verification and cleanup. Operator configuration and authorization must be supplied separately. Do not treat the package's source checks as a completed runtime test.

The [historical evidence](evidence/e2e-02/manifest.json) and adjacent `source/` describe the 5 October 2026 GST run: seven cases and 234 assertions. Its recorded PIDs, offsets and results do not establish a new run of the portable package. The [historical guide](historical/REPRODUCE.md) retains that run's original recipe status.
