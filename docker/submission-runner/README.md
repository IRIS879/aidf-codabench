# Custom Submission Runner Images

Recommended for survival submissions:
- use a modern Python image if you need `scikit-survival`
- keep the legacy `py37` image only if you specifically depend on that old stack

Modern image with:
- `lifelines`
- `scikit-survival` (`import sksurv`)
- `scikit-learn` (`import sklearn`)

```bash
docker build -f docker/submission-runner/Dockerfile.py310-survival -t my-codabench-survival .
```

Verify:

```bash
docker run --rm my-codabench-survival python -c "import lifelines, sksurv, sklearn; print(lifelines.__version__, sklearn.__version__)"
```

Then set your competition task `docker_image` to:

```text
my-codabench-survival
```

Legacy Python 3.7 image attempt with:
- `lifelines`
- `scikit-survival` (`import sksurv`)
- `scikit-learn` (`import sklearn`)

```bash
docker build -f docker/submission-runner/Dockerfile.py37-lifelines -t my-codabench-py37-lifelines .
```

Verify the package is available:

```bash
docker run --rm my-codabench-py37-lifelines python -c "import lifelines, sksurv, sklearn; print(lifelines.__version__, sklearn.__version__)"
```

If your workers run on another machine, tag and push it to a registry first.
