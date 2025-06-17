module.exports = {
  apps: [{
    name: 'smw-viewer',
    script: 'myenv/bin/python',
    args: '-m backend.app.tasks.task_manager',
    cwd: __dirname,
    interpreter: 'python',
    interpreter_args: '-u',
    env: {
      PYTHONPATH: '.',
    },
  }, {
    name: 'smw-viewer-api',
    script: 'myenv/bin/uvicorn',
    args: 'backend.app.main:app --host 0.0.0.0 --port 3004',
    cwd: __dirname,
    interpreter: 'python',
    interpreter_args: '-u',
    env: {
      PYTHONPATH: '.',
    },
  }],
};
