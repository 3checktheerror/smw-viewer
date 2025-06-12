module.exports = {
  apps: [{
    name: 'smw-viewer',
    script: 'myenv/bin/python',
    args: '-m backend.app.tasks.task_manager',
    cwd: __dirname,
    interpreter_args: '-u',
    env: {
      PYTHONPATH: '.',
    },
  }],
};
