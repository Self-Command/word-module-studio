"""GitHub Actions adapter for the shared explicit-file task runner."""
import os
from pathlib import Path
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from word_module_studio.runtime import require_actions, execution_scope, write_json
from word_module_studio.tasks import execute_task


if __name__ == '__main__':
    require_actions()
    folder = Path('build/task'); folder.mkdir(parents=True, exist_ok=True)
    try:
        with execution_scope('actions'):
            execute_task(Path(os.environ['WMS_INPUT_ROOT']) / os.environ['WMS_TASK_ID'], folder,
                task_id=os.environ['WMS_TASK_ID'], engine_commit=os.environ['WMS_ENGINE_COMMIT'])
    except Exception as exc:
        write_json(folder / 'task-failure.json', {'build_success': False, 'automatic_pass': False,
            'visual_review_complete': False, 'delivery_accepted': False, 'error': str(exc), 'traceback': traceback.format_exc()})
        raise
