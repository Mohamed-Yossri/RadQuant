# Contributing to RadQuant

Thank you for your interest in contributing to RadQuant! This project builds on
[MedRAX](https://github.com/bowang-lab/MedRAX) (ICML 2025) to create a
privacy-first, locally-deployable AI workstation for chest X-ray interpretation.

## ⚠️ Important: This is a Research Project

RadQuant is a **research/assistive demo, not a medical device**. Contributions
that could be interpreted as clinical claims must be clearly scoped as research.

## Getting Started

1. **Fork the repo** and clone your fork
2. **Set up the environment** — see the [README](README.md#-getting-started)
3. **Run the test suite** before making changes:
   ```bash
   pytest tests/ -v
   ```

## Development Workflow

### Branch Naming

- `feature/<name>` — new features
- `fix/<name>` — bug fixes
- `eval/<name>` — evaluation/benchmark work
- `docs/<name>` — documentation improvements

### Code Style

- **Python 3.10+** with type hints
- **Docstrings** on all public functions (Google style)
- Keep modules focused — one concern per file
- Use `radquant.config` for all credential/runtime resolution
- Model loading via singletons (see `radquant/models/medgemma.py`)

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_triage.py -v

# Per-phase verification
python scripts/phase3_check.py
```

### Commit Messages

Use clear, descriptive commit messages:
```
Phase N: brief description of what changed

- Detail 1
- Detail 2
```

## What We're Looking For

### High Priority
- Evaluation on the full 2,500-question ChestAgentBench
- CT modality support via MONAI bundles
- Multi-image (PA + lateral) joint analysis
- Urgency weight calibration studies

### Welcome Contributions
- Documentation improvements
- Test coverage expansion
- UI/UX improvements
- Performance optimizations
- Bug fixes

### Please Discuss First
- Architectural changes
- New model integrations
- New evaluation benchmarks
- Changes to the triage scoring system

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE).
