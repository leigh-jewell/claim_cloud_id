---

## 🧪 Refactor Validation (Phase 1)

If you are validating the first refactor phase (constants/config/CLI extraction), run:

```bash
uv run python -m py_compile main.py claim_cloud_id/constants.py claim_cloud_id/config.py claim_cloud_id/cli.py claim_cloud_id/logger.py claim_cloud_id/csv_loader.py claim_cloud_id/report_writer.py claim_cloud_id/api_operations.py claim_cloud_id/orchestrator.py
uv run python main.py --action check --csv cloud_id.csv
uv run python -m unittest discover -s tests -p "test_*.py"
```

These checks confirm the module extraction compiles and that the existing check workflow still runs.