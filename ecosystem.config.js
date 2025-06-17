module.exports = {
  apps: [{
    name: 'smw-viewer',
    script: '-m',
    args: 'backend.app.tasks.task_manager',
    cwd: __dirname,
    interpreter: './myenv/bin/python',
    interpreter_args: '-u',
    env: {
      PYTHONPATH: '.',
    },
  }, {
    name: 'smw-viewer-api',
    script: 'backend.app.main:app',
    args: '--host 0.0.0.0 --port 3004',
    cwd: __dirname,
    interpreter: './myenv/bin/uvicorn',
    env: {
      PYTHONPATH: '.',
    },
  }],
};
